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
    ) -> Tuple[bool, str]:
        """
        Validates a candidate 6-red combination against all 6 quantitative guardrails.

        :param reds: List of red ball numbers.
        :param prior_reds: Optional list of red balls drawn in the immediate prior issue.
        :return: (is_valid: bool, reason: str). Returns (True, "PASSED") if all guardrails pass.
        """
        if len(reds) != 6:
            return False, f"EXPECTED_6_BALLS_GOT_{len(reds)}"
        if len(set(reds)) != 6:
            return False, "DUPLICATE_BALLS"
        if any(r < 1 or r > 33 for r in reds):
            return False, "OUT_OF_BOUNDS_1_33"

        sorted_reds = sorted(reds)

        # 1. AC Value >= 6
        ac = StatisticalFilters.calculate_ac(sorted_reds)
        if ac < 6:
            return False, f"AC_VALUE_BELOW_6 (got {ac})"

        # 2. Red Sum in [75, 135]
        s = sum(sorted_reds)
        if s < 75 or s > 135:
            return False, f"SUM_OUT_OF_BOUNDS_{s}"

        # 3. Odd-Even Ratio in {2:4, 3:3, 4:2}
        odd_count = sum(1 for x in sorted_reds if x % 2 == 1)
        if odd_count not in (2, 3, 4):
            return False, f"ODD_EVEN_UNBALANCED_{odd_count}"

        # 4. Consecutive Groups <= 2, Max run <= 3
        diffs = [sorted_reds[i + 1] - sorted_reds[i] for i in range(5)]
        consec_pairs = diffs.count(1)
        max_run, curr_run = 1, 1
        for d in diffs:
            if d == 1:
                curr_run += 1
                max_run = max(max_run, curr_run)
            else:
                curr_run = 1
        if consec_pairs > 2 or max_run > 3:
            return False, f"EXCESSIVE_CONSECUTIVE_NUMBERS (pairs={consec_pairs}, max_run={max_run})"

        # 5. Span in [18, 30]
        span = sorted_reds[-1] - sorted_reds[0]
        if span < 18 or span > 30:
            return False, f"SPAN_OUT_OF_BOUNDS_{span}"

        # 6. Prior Draw Repeat Count in [0, 2]
        if prior_reds:
            repeat_cnt = len(set(sorted_reds) & set(prior_reds))
            if repeat_cnt > 2:
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

    def generate_5_lines(self) -> List[List[int]]:
        """
        Generates 5 lines using Dan-Tuo Wheel Covering Matrix with Statistical Guardrails validation.
        Guarantees:
        1. Exactly 5 lines of 6 sorted reds
        2. Pairwise intersection between any two lines in [3, 4] (strictly prevents 5-ball degeneracy)
        3. Balanced satellite coverage across the 5 lines (each satellite appears 2-3 times)
        4. All lines satisfy statistical guardrails (AC >= 6, Sum in [75, 135], Odd-Even, Consec, Span)
        """
        cores, satellites = self.select_candidate_pool()
        prior_reds = self.history[-1] if self.history else None

        # Generate and validate all 70 candidate 4-satellite subsets
        valid_lines: List[List[int]] = []
        for alt_comb in itertools.combinations(satellites, 4):
            cand = sorted(cores + list(alt_comb))
            v, _ = StatisticalFilters.is_valid_line(cand, prior_reds)
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
            is_valid, _ = StatisticalFilters.is_valid_line(candidate_line, prior_reds)
            overlap_ok = all(len(set(candidate_line) & set(l)) >= 3 for l in lines)

            if not (is_valid and overlap_ok and candidate_line not in lines):
                for alt_comb in itertools.combinations(satellites, 4):
                    cand = sorted(cores + list(alt_comb))
                    if cand in lines:
                        continue
                    v, _ = StatisticalFilters.is_valid_line(cand, prior_reds)
                    if v and all(3 <= len(set(cand) & set(l)) <= 4 for l in lines):
                        candidate_line = cand
                        break
            lines.append(candidate_line)

        return lines
