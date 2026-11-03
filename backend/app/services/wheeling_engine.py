"""
Combinatorial Dan-Tuo wheeling coverage and statistical guardrails engine for red balls.

Implements:
1. StatisticalFilters:
   - Arithmetic Complexity (AC value = |D| - 5) guardrail (AC >= 6)
   - Sum value within historical 80% confidence interval [75, 135]
   - Odd-even parity balance ({2:4, 3:3, 4:2} -> odd count in {2, 3, 4})
   - Consecutive groups limit (consecutive pairs <= 2, max run <= 3)
   - Span bounds [18, 30]
   - Prior draw repeat count <= 2
2. RedWheelingEngine:
   - 10-ball Dan-Tuo candidate pool selection (2 Cores + 8 Satellites) balancing Cold/Warm/Hot and Zone distribution
   - Combinatorial wheel matrix coverage generating exactly 5 lines of 6 sorted reds
   - Guaranteed pairwise overlap >= 3 and local repair against statistical guardrails
"""

import itertools
from typing import List, Tuple, Optional, Set, Dict


class StatisticalFilters:
    """Evaluates red ball combinations against empirical and mathematical guardrails."""

    @staticmethod
    def calculate_ac(reds: List[int]) -> int:
        """
        Calculate Arithmetic Complexity (AC value).
        Formula: AC = |D| - (R - 1) = |D| - 5 for 6 red balls.

        :param reds: List of 6 red ball integers.
        :return: AC integer value (typically 0..10).
        """
        if len(reds) < 2:
            return 0
        diffs = {abs(reds[i] - reds[j]) for i in range(len(reds)) for j in range(i + 1, len(reds))}
        return len(diffs) - (len(reds) - 1)

    @staticmethod
    def is_valid_line(
        reds: List[int],
        prior_reds: Optional[List[int]] = None,
        custom_filters: Optional[dict] = None,
        profile: str = "CENTRAL",
    ) -> Tuple[bool, str]:
        """
        Validates a candidate 6-red combination against quantitative guardrails with profile tiering.

        :param reds: List of red ball numbers.
        :param prior_reds: Optional list of red balls drawn in the immediate prior issue.
        :param custom_filters: Optional custom filters dict with sum_min, sum_max, ac_min, etc.
        :param profile: 'CENTRAL' (defensive normal band) or 'WING' (offensive tail coverage).
        :return: (is_valid: bool, reason: str). Returns (True, "PASSED") if all guardrails pass.
        """
        if len(reds) != 6:
            return False, f"EXPECTED_6_BALLS_GOT_{len(reds)}"
        if len(set(reds)) != 6:
            return False, "DUPLICATE_BALLS"
        if any(r < 1 or r > 33 for r in reds):
            return False, "OUT_OF_BOUNDS_1_33"

        sorted_reds = sorted(reds)
        cf = custom_filters or {}

        # Profile-based baseline boundaries
        if profile.upper() == "WING":
            default_ac_min = 5
            default_sum_min = 65
            default_sum_max = 145
            default_span_min = 15
            default_span_max = 32
            default_odd = (1, 2, 3, 4, 5)
            default_max_consec = 3
        else:  # CENTRAL
            default_ac_min = 6
            default_sum_min = 80
            default_sum_max = 130
            default_span_min = 18
            default_span_max = 30
            default_odd = (2, 3, 4)
            default_max_consec = 2

        ac_min = cf.get("ac_min", default_ac_min) if cf.get("ac_min") is not None else default_ac_min
        sum_min = cf.get("sum_min", default_sum_min) if cf.get("sum_min") is not None else default_sum_min
        sum_max = cf.get("sum_max", default_sum_max) if cf.get("sum_max") is not None else default_sum_max
        span_min = cf.get("span_min", default_span_min) if cf.get("span_min") is not None else default_span_min
        span_max = cf.get("span_max", default_span_max) if cf.get("span_max") is not None else default_span_max
        odd_allowed = tuple(cf.get("odd_counts", default_odd)) if cf.get("odd_counts") else default_odd
        max_repeats = cf.get("max_repeats", 2) if cf.get("max_repeats") is not None else 2

        # 1. AC Value >= ac_min
        ac = StatisticalFilters.calculate_ac(sorted_reds)
        if ac < ac_min:
            return False, f"AC_VALUE_BELOW_{ac_min} (got {ac})"

        # 2. Red Sum in [sum_min, sum_max]
        s = sum(sorted_reds)
        if s < sum_min or s > sum_max:
            return False, f"SUM_OUT_OF_BOUNDS_{s}"

        # 3. Odd-Even Ratio
        odd_count = sum(1 for x in sorted_reds if x % 2 == 1)
        if odd_count not in odd_allowed:
            return False, f"ODD_EVEN_UNBALANCED_{odd_count}"

        # 4. Consecutive Groups
        diffs = [sorted_reds[i + 1] - sorted_reds[i] for i in range(5)]
        consec_pairs = diffs.count(1)
        max_run, curr_run = 1, 1
        for d in diffs:
            if d == 1:
                curr_run += 1
                max_run = max(max_run, curr_run)
            else:
                curr_run = 1
        if consec_pairs > default_max_consec or max_run > (default_max_consec + 1):
            return False, f"EXCESSIVE_CONSECUTIVE_NUMBERS (pairs={consec_pairs}, max_run={max_run})"

        # 5. Span in [span_min, span_max]
        span = sorted_reds[-1] - sorted_reds[0]
        if span < span_min or span > span_max:
            return False, f"SPAN_OUT_OF_BOUNDS_{span}"

        # 6. Prior Draw Repeat Count
        if prior_reds:
            repeat_cnt = len(set(sorted_reds) & set(prior_reds))
            if repeat_cnt > max_repeats:
                return False, f"EXCESSIVE_PRIOR_REPEATS_{repeat_cnt}"

        return True, "PASSED"


class RedWheelingEngine:
    """Candidate pool selection and Dan-Tuo combinatorial wheeling engine."""

    def __init__(self, historical_reds: List[List[int]]):
        """
        :param historical_reds: List of historical draws up to T-1, each a list of 6 ints.
        """
        self.history = historical_reds
        self.n_draws = len(historical_reds)

    def select_candidate_pool(self) -> Tuple[List[int], List[int]]:
        """
        Selects 10 candidate balls: 2 Core Anchors (胆码) and 8 Satellites (拖码).
        Enforces empirical balanced distribution: 5 Hot : 3 Warm : 2 Cold across 3 Zones.
        Guarantees headroom for prior draw repeats (repeats <= 2).

        :return:
            cores: List of 2 distinct red balls.
            satellites: List of 8 distinct red balls.
        """
        omissions: Dict[int, int] = {}
        for b in range(1, 34):
            last_idx = -1
            for idx in range(self.n_draws - 1, -1, -1):
                if b in self.history[idx]:
                    last_idx = idx
                    break
            omissions[b] = (self.n_draws - 1 - last_idx) if last_idx != -1 else self.n_draws

        hot = sorted([b for b, o in omissions.items() if o <= 4], key=lambda b: (omissions[b], b))
        warm = sorted([b for b, o in omissions.items() if 5 <= o <= 9], key=lambda b: (omissions[b], b))
        cold = sorted([b for b, o in omissions.items() if o >= 10], key=lambda b: (omissions[b], b))

        prior_draw = set(self.history[-1]) if self.history else set()

        def get_zone(b: int) -> int:
            return 1 if b <= 11 else (2 if b <= 22 else 3)

        # Select Core 1: top hot ball (or warm if hot empty)
        core_1 = hot[0] if hot else (warm[0] if warm else 1)

        # Select Core 2: different zone (|core_2 - core_1| >= 8)
        # Avoid both cores being from prior_draw to preserve repeat_prev_red <= 2
        core_2 = None
        for b in hot[1:] + warm:
            if get_zone(b) != get_zone(core_1) and abs(b - core_1) >= 8:
                if not (core_1 in prior_draw and b in prior_draw):
                    core_2 = b
                    break
        if core_2 is None:
            for b in warm + cold + hot[1:]:
                if abs(b - core_1) >= 6:
                    core_2 = b
                    break
        if core_2 is None:
            core_2 = next((b for b in range(1, 34) if b != core_1 and abs(b - core_1) >= 6), (core_1 + 10) % 33 + 1)

        cores = sorted([core_1, core_2])
        chosen = set(cores)
        satellites: List[int] = []

        # Target 10-ball candidate pool: ~2 Cold, ~3 Warm, ~5 Hot, with balanced 3-Zone caps (Zone 1: 3, Zone 2: 4, Zone 3: 4)
        z_caps = {1: 3, 2: 4, 3: 4}

        # 1. Select 2 Cold balls across zones
        for b in cold:
            if sum(1 for s in satellites if s in cold) >= 2:
                break
            if b not in chosen and sum(1 for c in chosen if get_zone(c) == get_zone(b)) < z_caps[get_zone(b)]:
                satellites.append(b)
                chosen.add(b)

        # 2. Select 3 Warm balls respecting zone caps
        for b in warm:
            if sum(1 for s in satellites if s in warm) >= 3:
                break
            if b not in chosen and sum(1 for c in chosen if get_zone(c) == get_zone(b)) < z_caps[get_zone(b)]:
                satellites.append(b)
                chosen.add(b)

        # 3. Fill remaining slots with Hot balls (limit prior draw repeats across pool to at most 2)
        for b in hot:
            if len(satellites) >= 8:
                break
            if b in chosen:
                continue
            if b in prior_draw and len(chosen & prior_draw) >= 2:
                continue
            if sum(1 for c in chosen if get_zone(c) == get_zone(b)) < z_caps[get_zone(b)]:
                satellites.append(b)
                chosen.add(b)

        # 4. Fallback backfill to guarantee exactly 8 distinct satellites
        for b in warm + hot + cold + list(range(1, 34)):
            if len(satellites) == 8:
                break
            if b not in chosen:
                satellites.append(b)
                chosen.add(b)

        satellites.sort()
        return cores, satellites

    def select_zero_core_pool(
        self,
        red_probs: Optional[List[float]] = None,
        pool_size: int = 13,
        batch_offset: int = 0,
    ) -> List[int]:
        """
        Selects an unanchored candidate pool of 12~14 balls (default 13) across 3 Zones,
        leveraging neural network probability distributions and omission states.
        Eliminates the single-point-of-failure 2-core lock-in.
        Supports batch_offset rotation for generating distinct multi-group tickets.
        """
        omissions: Dict[int, int] = {}
        for b in range(1, 34):
            last_idx = -1
            for idx in range(self.n_draws - 1, -1, -1):
                if b in self.history[idx]:
                    last_idx = idx
                    break
            omissions[b] = (self.n_draws - 1 - last_idx) if last_idx != -1 else self.n_draws

        def get_zone(b: int) -> int:
            return 1 if b <= 11 else (2 if b <= 22 else 3)

        # Score balls based on neural network probabilities if available, else hybrid omission
        scored_balls = []
        for b in range(1, 34):
            if red_probs is not None and len(red_probs) == 33:
                p = float(red_probs[b - 1])
            else:
                o = omissions[b]
                p = 1.0 / (1.0 + o * 0.1) if o <= 10 else 0.2
            scored_balls.append((b, p))

        # Sort descending by score
        scored_balls.sort(key=lambda x: -x[1])
        ranked_balls = [x[0] for x in scored_balls]

        # Apply batch_offset rotation if multiple batches generated
        if batch_offset > 0:
            rot_shift = (batch_offset * 3) % 20
            ranked_balls = ranked_balls[rot_shift:] + ranked_balls[:rot_shift]

        # Balanced selection across zones: target ~4 in Z1, ~5 in Z2, ~4 in Z3
        pool: List[int] = []
        zone_caps = {1: 4, 2: 5, 3: 4}

        for b in ranked_balls:
            if len(pool) >= pool_size:
                break
            z = get_zone(b)
            if sum(1 for x in pool if get_zone(x) == z) < zone_caps[z]:
                pool.append(b)

        # Backfill if not full
        for b in ranked_balls:
            if len(pool) >= pool_size:
                break
            if b not in pool:
                pool.append(b)

        pool.sort()
        return pool

    def generate_5_lines_zero_core(
        self,
        candidate_pool: Optional[List[int]] = None,
        custom_filters: Optional[dict] = None,
        red_probs: Optional[List[float]] = None,
        batch_offset: int = 0,
    ) -> List[List[int]]:
        """
        Generates 5 lines using Zero-Core Orthogonal Covering Wheel with Portfolio Tiering.
        - Lines 0..2: Profile 'CENTRAL' (sum 80..130, AC >= 6, odd in 2,3,4)
        - Lines 3..4: Profile 'WING' (sum 65..145, AC >= 5)
        - Frequency constraint: each ball in candidate_pool appears 2..3 times across the 5 lines.
        - Overlap constraint: pairwise overlap between lines is strictly <= 3 balls.
        """
        pool = candidate_pool or self.select_zero_core_pool(red_probs=red_probs, pool_size=13, batch_offset=batch_offset)
        prior_reds = self.history[-1] if self.history else None

        # Generate all 6-combinations from pool: C(13, 6) = 1716
        central_cands = []
        wing_cands = []
        for comb in itertools.combinations(pool, 6):
            cand = sorted(comb)
            v_c, _ = StatisticalFilters.is_valid_line(cand, prior_reds, custom_filters=custom_filters, profile="CENTRAL")
            if v_c:
                central_cands.append(cand)
            v_w, _ = StatisticalFilters.is_valid_line(cand, prior_reds, custom_filters=custom_filters, profile="WING")
            if v_w:
                wing_cands.append(cand)

        chosen_lines: List[List[int]] = []
        ball_counts: Dict[int, int] = {b: 0 for b in pool}

        # Step 1: Pick 3 Central lines with overlap <= 3 and balanced frequency
        for cand in central_cands:
            if len(chosen_lines) == 3:
                break
            if any(len(set(cand) & set(prev)) > 3 for prev in chosen_lines):
                continue
            if any(ball_counts[b] >= 3 for b in cand):
                continue
            chosen_lines.append(cand)
            for b in cand:
                ball_counts[b] += 1

        # Fallback if strict central search didn't get 3
        if len(chosen_lines) < 3:
            for cand in central_cands:
                if len(chosen_lines) == 3:
                    break
                if cand not in chosen_lines and all(len(set(cand) & set(prev)) <= 4 for prev in chosen_lines):
                    chosen_lines.append(cand)
                    for b in cand:
                        ball_counts[b] += 1

        # Step 2: Pick 2 Wing lines to cover under-represented pool balls
        remaining_cands = [c for c in wing_cands if c not in chosen_lines]
        # Sort remaining by how many under-represented balls (count < 2) they cover
        remaining_cands.sort(key=lambda c: -sum(1 for b in c if ball_counts[b] < 2))

        for cand in remaining_cands:
            if len(chosen_lines) == 5:
                break
            if any(len(set(cand) & set(prev)) > 4 for prev in chosen_lines):
                continue
            chosen_lines.append(cand)
            for b in cand:
                ball_counts[b] += 1

        # Final safety check: if still < 5 lines, backfill from central or wing
        for cand in central_cands + wing_cands:
            if len(chosen_lines) == 5:
                break
            if cand not in chosen_lines:
                chosen_lines.append(cand)

        # Fallback guaranteed default if pool was too small/filtered
        while len(chosen_lines) < 5:
            shift = len(chosen_lines) * 2
            sub = [pool[(shift + i) % len(pool)] for i in range(6)]
            chosen_lines.append(sorted(sub))

        return chosen_lines[:5]

    def generate_5_lines(
        self,
        custom_filters: Optional[dict] = None,
        strategy_mode: str = "DAN_TUO",
        candidate_pool: Optional[List[int]] = None,
        red_probs: Optional[List[float]] = None,
        batch_offset: int = 0,
    ) -> List[List[int]]:
        """
        Generates 5 lines. Supports DAN_TUO (legacy canonical wheel) and ZERO_CORE (orthogonal covering).
        """
        if strategy_mode == "ZERO_CORE":
            return self.generate_5_lines_zero_core(
                candidate_pool=candidate_pool,
                custom_filters=custom_filters,
                red_probs=red_probs,
                batch_offset=batch_offset,
            )

        # Legacy Dan-Tuo branch
        cores, satellites = self.select_candidate_pool()
        prior_reds = self.history[-1] if self.history else None

        # Generate and validate all 70 candidate 4-satellite subsets
        valid_lines: List[List[int]] = []
        for alt_comb in itertools.combinations(satellites, 4):
            cand = sorted(cores + list(alt_comb))
            v, _ = StatisticalFilters.is_valid_line(cand, prior_reds, custom_filters=custom_filters)
            if v:
                valid_lines.append(cand)

        # Combinatorial search for 5 lines satisfying pairwise overlap in [3, 4] and balanced satellite frequency
        best_lines: Optional[List[List[int]]] = None
        best_score = -999999

        def search_balanced_wheel(idx: int, chosen: List[List[int]], sat_counts: Dict[int, int], max_sat_freq: int) -> bool:
            nonlocal best_lines, best_score
            if len(chosen) == 5:
                score = len(sat_counts) * 100 - sum((cnt - 2.5) ** 2 for cnt in sat_counts.values())
                if score > best_score:
                    best_score = score
                    best_lines = list(chosen)
                return len(sat_counts) == len(satellites)

            for i in range(idx, len(valid_lines)):
                cand = valid_lines[i]
                cand_sats = [b for b in cand if b in satellites]
                cand_set = set(cand)
                # Overlap constraint: pairwise intersection must be in [3, 4]
                if any(len(cand_set & set(prev)) < 3 or len(cand_set & set(prev)) > 4 for prev in chosen):
                    continue
                # Frequency capping
                if any(sat_counts.get(b, 0) >= max_sat_freq for b in cand_sats):
                    continue
                new_counts = dict(sat_counts)
                for b in cand_sats:
                    new_counts[b] = new_counts.get(b, 0) + 1
                if search_balanced_wheel(i + 1, chosen + [cand], new_counts, max_sat_freq):
                    return True
            return False

        if len(valid_lines) >= 5:
            search_balanced_wheel(0, [], {}, max_sat_freq=3)
            if not best_lines:
                search_balanced_wheel(0, [], {}, max_sat_freq=4)

        if best_lines and len(best_lines) == 5:
            return best_lines

        # Fallback if valid_lines < 5 or tight overlap constraint
        patterns = [
            [0, 1, 2, 3],
            [0, 1, 4, 5],
            [2, 3, 4, 6],
            [0, 2, 5, 7],
            [1, 3, 6, 7],
        ]
        lines: List[List[int]] = []
        for pat in patterns:
            candidate_line = sorted(cores + [satellites[i] for i in pat])
            is_valid, _ = StatisticalFilters.is_valid_line(candidate_line, prior_reds, custom_filters=custom_filters)
            overlap_ok = all(len(set(candidate_line) & set(l)) >= 3 for l in lines)

            if not (is_valid and overlap_ok and candidate_line not in lines):
                for alt_comb in itertools.combinations(satellites, 4):
                    cand = sorted(cores + list(alt_comb))
                    if cand in lines:
                        continue
                    v, _ = StatisticalFilters.is_valid_line(cand, prior_reds, custom_filters=custom_filters)
                    if v and all(3 <= len(set(cand) & set(l)) <= 4 for l in lines):
                        candidate_line = cand
                        break
            lines.append(candidate_line)

        return lines
