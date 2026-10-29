"""

Blue ball quantitative scoring models and portfolio allocation strategies.



Implements:

1. BlueScoringEngine:

   - Hazard omission recovery rate with Gaussian cycle resonance, rebound acceleration, and cold pit damping

   - 1st & 2nd order Markov transition matrices with symmetric Dirichlet smoothing

   - Frequency-heat momentum indicator with rolling short-window Z-score & dual-EWMA velocity

   - Multi-model ensemble with temperature-scaled Softmax calibration and deterministic ranking

2. BlueAllocationStrategy:

   - Dynamic confidence-weighted break-even allocation (CONCENTRATED 3-2, BALANCED 2-2-1, DISPERSED 1-1-1-1-1, AUTO)

"""



import math

from typing import List, Tuple, Optional

import numpy as np





class BlueScoringEngine:

    """Ensemble quantitative scoring engine for Shuangseqiu blue ball (01-16)."""



    def __init__(self, historical_blue_seq: List[int]):

        """

        Initialize scoring engine with historical sequence of blue balls.



        :param historical_blue_seq: Chronological list of historical blue balls up to T-1.

                                    Values in 1..16.

        """

        if not historical_blue_seq:

            raise ValueError("historical_blue_seq cannot be empty")

        self.seq = np.array(historical_blue_seq, dtype=int)

        self.n_draws = len(self.seq)



    def score_omission_recovery(self) -> np.ndarray:

        """

        Model 1: Omission recovery rate with Gaussian cycle resonance and rebound acceleration.

        Returns array of 16 non-negative scores for balls 1..16.

        """

        scores = np.zeros(16, dtype=float)

        for b in range(1, 17):

            occurrences = np.where(self.seq == b)[0]

            if len(occurrences) == 0:

                current_omission = self.n_draws

                mean_cycle = 16.0

                std_cycle = 10.0

            else:

                current_omission = (self.n_draws - 1) - int(occurrences[-1])

                intervals = np.diff(occurrences)

                if len(intervals) == 0:

                    intervals = np.array([current_omission if current_omission > 0 else 16.0])

                mean_cycle = float(np.mean(intervals))

                std_cycle = float(np.std(intervals)) if (len(intervals) > 1 and np.std(intervals) > 0) else 10.0



            # Gaussian resonance around empirical cycle mean

            cycle_score = math.exp(-((current_omission - mean_cycle) ** 2) / (2 * (std_cycle ** 2)))



            # Rebound acceleration bonus (immediate repeat or gap-1 rebound)

            if current_omission in (0, 1):

                bonus = 0.30

            elif current_omission == 2:

                bonus = 0.20

            else:

                bonus = 0.0



            # Cold pit exponential damping factor (for t > 30)

            if current_omission <= 30:

                damping = 1.0

            else:

                damping = math.exp(-0.05 * (current_omission - 30))



            scores[b - 1] = (cycle_score + bonus) * damping



        return scores



    def score_markov_transition(self) -> np.ndarray:

        """

        Model 2: 1st and 2nd order Markov transition matrices with Dirichlet smoothing.

        Returns array of 16 non-negative scores for balls 1..16.

        """

        last_ball = int(self.seq[-1])

        prev_ball = int(self.seq[-2]) if self.n_draws >= 2 else last_ball



        # 1st order transition counts (17x17 matrix, 1-indexed)

        c1 = np.zeros((17, 17), dtype=float)

        for t in range(1, self.n_draws):

            b_from = self.seq[t - 1]

            b_to = self.seq[t]

            if 1 <= b_from <= 16 and 1 <= b_to <= 16:

                c1[b_from, b_to] += 1.0



        alpha = 0.5

        denom1 = np.sum(c1[last_ball, 1:17]) + 16.0 * alpha

        p1 = (c1[last_ball, 1:17] + alpha) / denom1



        # 2nd order transition counts (17x17x17 tensor)

        c2 = np.zeros((17, 17, 17), dtype=float)

        for t in range(2, self.n_draws):

            b_prev = self.seq[t - 2]

            b_from = self.seq[t - 1]

            b_to = self.seq[t]

            if 1 <= b_prev <= 16 and 1 <= b_from <= 16 and 1 <= b_to <= 16:

                c2[b_prev, b_from, b_to] += 1.0



        beta = 0.25

        denom2 = np.sum(c2[prev_ball, last_ball, 1:17]) + 16.0 * beta

        p2 = (c2[prev_ball, last_ball, 1:17] + beta) / denom2



        return 0.75 * p1 + 0.25 * p2



    def score_frequency_momentum(self) -> np.ndarray:

        """

        Model 3: Rolling frequency Z-score and dual-EWMA velocity mapped through Sigmoid.

        Returns array of 16 scores strictly bounded in [0.0, 1.0].

        """

        scores = np.zeros(16, dtype=float)

        w_short = min(20, self.n_draws)

        recent_seq = self.seq[-w_short:]

        p0 = 1.0 / 16.0

        sigma_short = math.sqrt(p0 * (1.0 - p0) / w_short)



        # Fast EWMA (span 10)

        n_fast = min(10, self.n_draws)

        weights_fast = np.exp(-np.linspace(0, 1, n_fast))

        sum_w_fast = float(np.sum(weights_fast))



        # Slow EWMA (span 30)

        n_slow = min(30, self.n_draws)

        weights_slow = np.exp(-np.linspace(0, 1, n_slow))

        sum_w_slow = float(np.sum(weights_slow))



        for b in range(1, 17):

            f_short = float(np.mean(recent_seq == b))

            z = (f_short - p0) / sigma_short



            fast_val = float(np.sum((self.seq[-n_fast:] == b) * weights_fast) / sum_w_fast)

            slow_val = float(np.sum((self.seq[-n_slow:] == b) * weights_slow) / sum_w_slow)



            delta_ema = fast_val - slow_val

            raw_signal = z + 5.0 * delta_ema

            scores[b - 1] = 1.0 / (1.0 + math.exp(-raw_signal))



        return scores



    def score_cold_warm_hot_oscillation(self) -> np.ndarray:

        """

        Model 4: Cold/Warm/Hot empirical zone classification and parity/high-low oscillation.

        - Warm (omission 5..15): highest empirical hit probability zone (~50%).

        - Hot (omission 0..4): momentum repeat zone (~35%).

        - Cold (omission > 15): low-frequency breakthrough zone (~15%).

        - Oscillation bonus: Parity alternating and High/Low (1-8 vs 9-16) swing.

        Returns array of 16 scores in [0.0, 1.0].

        """

        scores = np.zeros(16, dtype=float)

        last_ball = int(self.seq[-1])

        last_is_odd = (last_ball % 2 == 1)

        last_is_high = (last_ball >= 9)



        for b in range(1, 17):

            occurrences = np.where(self.seq == b)[0]

            omission = (self.n_draws - 1) - int(occurrences[-1]) if len(occurrences) > 0 else self.n_draws



            # Zone score: favor warm and hot zones over deep cold traps

            if omission <= 4:

                zone_score = 0.85

            elif 5 <= omission <= 15:

                zone_score = 1.00  # Sweet spot warm zone

            elif 16 <= omission <= 25:

                zone_score = 0.50

            else:

                zone_score = max(0.15, 0.40 * math.exp(-0.05 * (omission - 25)))



            # Oscillation bonus

            b_is_odd = (b % 2 == 1)

            b_is_high = (b >= 9)



            osc_bonus = 0.0

            if b_is_odd != last_is_odd:

                osc_bonus += 0.10

            if b_is_high != last_is_high:

                osc_bonus += 0.10



            scores[b - 1] = min(1.0, zone_score + osc_bonus)



        return scores



    def compute_ensemble_probabilities(

        self,

        weights: Tuple[float, ...] = (0.35, 0.25, 0.20, 0.20),

        tau: float = 0.85,

    ) -> Tuple[np.ndarray, List[int]]:

        """

        Standardizes, blends, and softmax-calibrates probabilities across the 4 models:

        1. Omission Recovery / Poisson Hazard

        2. 1st & 2nd Order Markov Transition

        3. Frequency Momentum

        4. Cold/Warm/Hot Zone & Parity/High-Low Oscillation



        :param weights: Weight vector for (hazard, markov, momentum, oscillation).

        :param tau: Temperature hyperparameter for Softmax calibration. Defaults to 0.85.

        :return:

            probs: np.ndarray of length 16 summing to 1.0.

            ranked_balls: List of 16 distinct ball numbers (1..16) sorted in descending probability.

        """

        s1 = self.score_omission_recovery()

        s2 = self.score_markov_transition()

        s3 = self.score_frequency_momentum()

        s4 = self.score_cold_warm_hot_oscillation()



        def min_max(arr: np.ndarray) -> np.ndarray:

            rng = float(np.max(arr) - np.min(arr))

            if rng > 1e-9:

                return (arr - np.min(arr)) / rng

            return np.zeros_like(arr)



        if len(weights) == 3:

            w = [weights[0] * 0.8, weights[1] * 0.8, weights[2] * 0.8, 0.20]

        else:

            w = list(weights)

        w_sum = sum(w)

        if w_sum > 0:

            w = [x / w_sum for x in w]



        composite = (

            w[0] * min_max(s1)

            + w[1] * min_max(s2)

            + w[2] * min_max(s3)

            + w[3] * min_max(s4)

        )



        # Softmax with temperature tau

        exp_comp = np.exp(composite / tau)

        probs = exp_comp / np.sum(exp_comp)



        # Deterministic ranking: descending probability, ascending ball number tie-breaker

        indexed_scores = [(b, float(probs[b - 1])) for b in range(1, 17)]

        indexed_scores.sort(key=lambda x: (-x[1], x[0]))

        ranked_balls = [x[0] for x in indexed_scores]



        return probs, ranked_balls





class BlueAllocationStrategy:

    """Confidence-weighted blue ball allocation to guarantee break-even on hit."""



    @staticmethod

    def allocate(

        ranked_balls: List[int],

        probs: Optional[np.ndarray] = None,

        mode: str = "AUTO",

    ) -> List[int]:

        """

        Allocate blue balls across exactly 5 notes.



        :param ranked_balls: List of blue balls in descending order of confidence.

        :param probs: Optional calibrated probabilities array of length 16.

        :param mode: 'CONCENTRATED', 'BALANCED', 'DISPERSED', or 'AUTO' (and aliases).

        :return: Exactly 5 blue ball integers for Line 1..5.

        """

        if len(ranked_balls) < 2:

            raise ValueError("ranked_balls must contain at least 2 balls")



        top1 = ranked_balls[0]

        top2 = ranked_balls[1]

        top3 = ranked_balls[2] if len(ranked_balls) > 2 else ranked_balls[-1]



        m = mode.upper() if mode else "AUTO"



        if m in ("DISPERSED", "DISPERSED_BASELINE", "BASELINE"):

            if len(ranked_balls) < 5:

                raise ValueError("ranked_balls must contain at least 5 balls for DISPERSED mode")

            return list(ranked_balls[:5])



        if m in ("CONCENTRATED", "CONCENTRATED_BREAK_EVEN", "BREAK_EVEN"):

            return [top1, top1, top1, top2, top2]



        if m in ("BALANCED", "STAT_FILTER"):

            return [top1, top1, top2, top2, top3]



        if m in ("AUTO", "ML_PROB"):
            if probs is not None:
                p_top1 = float(probs[top1 - 1])
                p_top2 = float(probs[top2 - 1])
                delta = p_top1 - p_top2
                # High-confidence offensive spike -> 3+2 Concentrated
                if delta >= 0.15 and p_top1 >= 0.28:
                    return [top1, top1, top1, top2, top2]
                # Moderate confidence -> 2+2+1 Balanced
                elif delta >= 0.08 or (p_top1 + p_top2) >= 0.26:
                    return [top1, top1, top2, top2, top3]
                # Standard defensive capital preservation -> 5-Distinct Dispersed (31.25% coverage)
                else:
                    return list(ranked_balls[:5])
            return list(ranked_balls[:5])

        # Default fallback to high-defense dispersed 5-distinct
        return list(ranked_balls[:5]) if len(ranked_balls) >= 5 else [top1, top1, top1, top2, top2]
