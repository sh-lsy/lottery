"""
backend/app/services/metaphysics_engine.py

Zhouyi Bagua, Hetu-Luoshu, and Five-Elements (Wuxing) Metaphysics Engine:
1. Solar Date -> Sixty Jiazi (TianGan & DiZhi) Calendar Conversion.
2. Hetu-Luoshu Red & Blue Ball Wuxing Classification (Water, Fire, Wood, Metal, Earth).
3. Nine-Palace (Jiugong) Bagua Modulo Mapping (Kan, Kun, Zhen, Xun, Central, Qian, Dui, Gen, Li).
4. Ten Gods (Shishen) Affinity & Inter-promoting/restraining Cycle with Day Master.
5. Meihua Yishu (Plum Blossom Oracle) Hexagram Generation & Prophecy Text.
6. Metaphysics Prior Probability Distribution Vector for Red (1..33) and Blue (1..16).
"""

from datetime import date, datetime
from typing import Dict, List, Tuple, Any, Optional


TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# Sixty Jiazi
SIXTY_JIAZI = [TIANGAN[i % 10] + DIZHI[i % 12] for i in range(60)]

# TianGan Wuxing
TIANGAN_WUXING = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

# DiZhi Wuxing
DIZHI_WUXING = {
    "寅": "木", "卯": "木",
    "巳": "火", "午": "火",
    "辰": "土", "戌": "土", "丑": "土", "未": "土",
    "申": "金", "酉": "金",
    "亥": "水", "子": "水",
}

# 12 DiZhi to Triad Element:
# 申子辰 -> 水局, 亥卯未 -> 木局, 寅午戌 -> 火局, 巳酉丑 -> 金局
DIZHI_TRIADS = {
    "申": "水", "子": "水", "辰": "水",
    "亥": "木", "卯": "木", "未": "木",
    "寅": "火", "午": "火", "戌": "火",
    "巳": "金", "酉": "金", "丑": "金",
}

# DiZhi Six Harmony Pairs:
DIZHI_SIX_HARMONY = {
    "子": "丑", "丑": "子",
    "寅": "亥", "亥": "寅",
    "卯": "戌", "戌": "卯",
    "辰": "酉", "酉": "辰",
    "巳": "申", "申": "巳",
    "午": "未", "未": "午",
}

TRIGRAM_ELEMENTS = {
    "乾": "金", "兑": "金", "离": "火", "震": "木",
    "巽": "木", "坎": "水", "艮": "土", "坤": "土",
}

TRIGRAM_LINES = {
    "乾": [1, 1, 1], "兑": [1, 1, 0], "离": [1, 0, 1], "震": [1, 0, 0],
    "巽": [0, 1, 1], "坎": [0, 1, 0], "艮": [0, 0, 1], "坤": [0, 0, 0],
}

LINES_TO_TRIGRAM = {tuple(v): k for k, v in TRIGRAM_LINES.items()}


def get_ball_dizhi(ball_num: int) -> str:
    """Returns Earthly Branch for ball number (1..33) modulo 12."""
    rem = (ball_num - 1) % 12
    return DIZHI[rem]


# Wuxing to Element Index: 金:0, 木:1, 水:2, 火:3, 土:4
WUXING_INDEX = {"金": 0, "木": 1, "水": 2, "火": 3, "土": 4}

# Hetu-Luoshu Number Wuxing:
# 1, 6 -> 水; 2, 7 -> 火; 3, 8 -> 木; 4, 9 -> 金; 5, 0 -> 土
def get_ball_wuxing(ball_num: int) -> str:
    rem = ball_num % 10
    if rem in (1, 6):
        return "水"
    elif rem in (2, 7):
        return "火"
    elif rem in (3, 8):
        return "木"
    elif rem in (4, 9):
        return "金"
    else:
        return "土"


# Jiugong Nine-Star Modulo 9 Bagua
# 1: 坎(水), 2: 坤(土), 3: 震(木), 4: 巽(木), 5: 中宫(土), 6: 乾(金), 7: 兑(金), 8: 艮(土), 9/0: 离(火)
JIUGONG_BAGUA = {
    1: {"trigram": "坎", "element": "水", "direction": "正北", "desc": "一白水星·潜龙勿用"},
    2: {"trigram": "坤", "element": "土", "direction": "西南", "desc": "二黑土星·厚德载物"},
    3: {"trigram": "震", "element": "木", "direction": "正东", "desc": "三碧木星·万物出震"},
    4: {"trigram": "巽", "element": "木", "direction": "东南", "desc": "四绿木星·风行天下"},
    5: {"trigram": "中宫", "element": "土", "direction": "中央", "desc": "五黄土星·太极枢纽"},
    6: {"trigram": "乾", "element": "金", "direction": "西北", "desc": "六白金星·飞龙在天"},
    7: {"trigram": "兑", "element": "金", "direction": "正西", "desc": "七赤金星·悦泽亨通"},
    8: {"trigram": "艮", "element": "土", "direction": "东北", "desc": "八白土星·动静不失"},
    0: {"trigram": "离", "element": "火", "direction": "正南", "desc": "九紫火星·离火生明"},
}

# Bagua Trigram Binary Representation (Bottom to Top: 0=Yin, 1=Yang)
# Qian=111(1), Dui=110(2), Li=101(3), Zhen=100(4), Xun=011(5), Kan=010(6), Gen=001(7), Kun=000(8)
EARLY_BAGUA_NAMES = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]

HEXAGRAM_NAMES = [
    "乾为天", "坤为地", "水雷屯", "山水蒙", "水天需", "天水讼", "地水师", "水地比",
    "风天小畜", "天泽履", "地天泰", "天地否", "天火同人", "火天大有", "地山谦", "雷地豫",
    "泽雷随", "山风蛊", "地泽临", "风地观", "火雷噬嗑", "山火贲", "山地剥", "地雷复",
    "天雷无妄", "山天大畜", "山雷颐", "泽风大过", "坎为水", "离为火", "泽山咸", "雷风恒",
    "天山遁", "雷天大壮", "火地晋", "地火明夷", "风火家人", "火泽睽", "水山蹇", "雷水解",
    "山泽损", "风雷益", "泽天夬", "天风姤", "泽地萃", "地风升", "泽水困", "水风井",
    "泽火革", "火风鼎", "震为雷", "艮为山", "风山渐", "雷泽归妹", "雷火丰", "火山旅",
    "巽为风", "兑为泽", "风水涣", "水泽节", "风泽中孚", "雷山小过", "水火既济", "火水未济"
]

HEXAGRAM_PROPHECIES = {
    "地天泰": "【上上卦·吉亨】天地交泰，内阳外阴，财源广进，通达之象。",
    "火天大有": "【上上卦·顺天】日丽中天，富厚顺遂，吉星高照，必有所获。",
    "水天需": "【中上卦·待时】云升于天，利涉大川，沉潜有备，蓄力大发。",
    "地山谦": "【上上卦·大吉】天道亏盈而益谦，地道变盈而流谦，谦和得财。",
    "天泽履": "【中平卦·慎行】履虎尾而不咥人，循序正道，克己致胜。",
    "水雷屯": "【中平卦·破土】云雷初发，破土萌芽，守正待变，后福无疆。",
    "雷地豫": "【上上卦·乐亨】雷出地奋，顺以动之，天地开泰，财禄亨通。",
    "水火既济": "【吉卦·圆满】水在火上，既济亨小，合化有功，收割之辰。",
}


class MetaphysicsEngine:
    """Computes GanZhi astrology, Hetu-Luoshu Wuxing affinity, and Bagua prophecy."""

    REFERENCE_DATE = date(2000, 1, 1)  # 2000-01-01 was 戊午 (Index 54 in 60 Jiazi)
    REFERENCE_INDEX = 54

    @classmethod
    def get_day_ganzhi(cls, dt: date) -> Tuple[str, str, str]:
        """
        Returns (DayGanZhi, TianGan, DiZhi) for any Gregorian date.
        e.g. ('甲辰', '甲', '辰')
        """
        delta = (dt - cls.REFERENCE_DATE).days
        gz_idx = (cls.REFERENCE_INDEX + delta) % 60
        gz_name = SIXTY_JIAZI[gz_idx]
        return gz_name, gz_name[0], gz_name[1]

    @classmethod
    def calculate_ten_gods_relation(cls, day_gan: str, ball_num: int) -> Tuple[str, float]:
        """
        Computes the relationship between Day Master TianGan and ball's Hetu-Luoshu Wuxing.
        Returns: (TenGodName, AffinityWeight)
        - 财星 (Wealth): I control, +25%
        - 印星 (Resource): Generates me, +20%
        - 食伤 (Output): I generate, +15%
        - 比劫 (Peer): Same element, +10%
        - 官杀 (Officer): Controls me, +5%
        """
        day_element = TIANGAN_WUXING[day_gan]
        ball_element = get_ball_wuxing(ball_num)

        # Generating cycle: 木生火, 火生土, 土生金, 金生水, 水生木
        promotes = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
        # Restraining cycle: 金克木, 木克土, 土克水, 水克火, 火克金
        restrains = {"金": "木", "木": "土", "土": "水", "水": "火", "火": "金"}

        if day_element == ball_element:
            return "比劫帮身", 1.10
        elif promotes[ball_element] == day_element:
            return "印绶生身", 1.20
        elif promotes[day_element] == ball_element:
            return "食伤泄秀", 1.15
        elif restrains[day_element] == ball_element:
            return "偏正财星", 1.25
        else:
            return "官杀克身", 1.05

    @classmethod
    def compute_metaphysics_probabilities(
        cls,
        draw_date_str: str,
        issue_no: str,
    ) -> Tuple[List[float], List[float], Dict[str, Any]]:
        """
        Computes 33 Red and 16 Blue prior probability distributions based on:
        - Day GanZhi Wuxing and Hai-Hour (21:15, Water hour) synergy.
        - Hetu-Luoshu Element affinity (Wealth, Resource, Output, Peer).
        - Jiugong Star Modulo harmony.

        Returns:
            red_probs: list of 33 floats summing to ~1.0
            blue_probs: list of 16 floats summing to 1.0
            metadata: astrological details (GanZhi, Wuxing, Hexagram prophecy)
        """
        try:
            if "-" in draw_date_str:
                parts = [int(p) for p in draw_date_str.split("-")]
                dt = date(parts[0], parts[1], parts[2])
            else:
                dt = datetime.strptime(draw_date_str[:8], "%Y%m%d").date()
        except Exception:
            dt = date.today()

        day_gz, day_gan, day_zhi = cls.get_day_ganzhi(dt)
        day_wuxing = TIANGAN_WUXING[day_gan]
        zhi_wuxing = DIZHI_WUXING[day_zhi]

        # SSQ always draws at 21:15 (Hai hour: Water element)
        hour_wuxing = "水"

        # Generating cycle: 木生火, 火生土, 土生金, 金生水, 水生木
        promotes = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
        # Restraining cycle: 金克木, 木克土, 土克水, 水克火, 火克金
        restrains = {"金": "木", "木": "土", "土": "水", "水": "火", "火": "金"}

        # Meihua Yishu Hexagram, Dongyao, and Bian Gua Calculation
        try:
            issue_int = sum(int(c) for c in str(issue_no) if c.isdigit())
        except Exception:
            issue_int = 18

        upper_num = (dt.year + dt.month + dt.day) % 8
        lower_num = (dt.year + dt.month + dt.day + 12 + issue_int) % 8  # 12 is Hai hour
        dongyao = (dt.year + dt.month + dt.day + 12 + issue_int) % 6 + 1  # Changing line 1..6

        up_name = EARLY_BAGUA_NAMES[upper_num]
        low_name = EARLY_BAGUA_NAMES[lower_num]
        hex_lines = TRIGRAM_LINES[low_name] + TRIGRAM_LINES[up_name]

        # Bian Gua (Transformed Hexagram via Dongyao bit flip)
        bian_lines = list(hex_lines)
        bian_lines[dongyao - 1] = 1 - bian_lines[dongyao - 1]
        bian_low = LINES_TO_TRIGRAM.get(tuple(bian_lines[:3]), low_name)
        bian_up = LINES_TO_TRIGRAM.get(tuple(bian_lines[3:]), up_name)

        # Hu Gua (Nuclear Hexagram: lines 2,3,4 and 3,4,5)
        hu_low = LINES_TO_TRIGRAM.get(tuple(hex_lines[1:4]), low_name)
        hu_up = LINES_TO_TRIGRAM.get(tuple(hex_lines[2:5]), up_name)

        # Auspicious elements from Bian Gua & Hu Gua
        bian_element = TRIGRAM_ELEMENTS.get(bian_up if dongyao <= 3 else bian_low, "金")
        hu_element = TRIGRAM_ELEMENTS.get(hu_up, "水")

        hex_idx = (upper_num * 8 + lower_num) % len(HEXAGRAM_NAMES)
        hex_name = HEXAGRAM_NAMES[hex_idx]

        def get_wuxing_energy(ball_num: int, is_blue: bool = False) -> float:
            bw = get_ball_wuxing(ball_num)
            b_zhi = get_ball_dizhi(ball_num)

            # 1. Ten Gods affinity base score
            if restrains[day_wuxing] == bw:
                score = 2.4  # 偏正财星 (primary wealth affinity)
            elif promotes[bw] == day_wuxing:
                score = 2.0  # 印绶生身 (resource nourishment)
            elif promotes[day_wuxing] == bw:
                score = 1.6  # 食伤生财 (output creating wealth)
            elif day_wuxing == bw:
                score = 1.1  # 比劫帮身 (peer support)
            else:
                score = 0.2  # 官杀克身 (officer restraint)

            # 2. Hai hour harmony (water generates wood, supported by metal)
            if bw in ("水", "木"):
                score += 0.8
            elif bw == "金":
                score += 0.5
            elif bw == "土":
                score -= 0.4  # Earth blocks water

            # 3. Jiugong Modulo resonance
            star = JIUGONG_BAGUA[ball_num % 9]
            if star["element"] in (day_wuxing, hour_wuxing):
                score += 0.4

            # 4. Earthly Branch Six Harmony & Three Harmonies Resonance
            if DIZHI_SIX_HARMONY.get(day_zhi) == b_zhi:
                score += 0.6  # 六合贵人吉星
            if DIZHI_TRIADS.get(day_zhi) == DIZHI_TRIADS.get(b_zhi):
                score += 0.5  # 三合局气运共振

            # 5. Meihua Yishu Bian Gua & Hu Gua auspicious resonance
            if bw == bian_element:
                score += 0.5  # 变卦用神相生
            if bw == hu_element:
                score += 0.3  # 互卦暗藏机运

            # 6. Blue ball Kan Water / Dui Metal resonance
            if is_blue:
                if bw == "水":
                    score += 1.2
                elif bw == "金":
                    score += 0.8

            return score

        # 1. Score 33 Red Balls using Softmax Temperature Scaling (tau = 0.45)
        tau = 0.45
        import numpy as np
        red_energies = np.array([get_wuxing_energy(b, is_blue=False) for b in range(1, 34)], dtype=float)
        exp_r = np.exp((red_energies - np.max(red_energies)) / tau)
        red_probs = (exp_r / np.sum(exp_r)).tolist()

        # 2. Score 16 Blue Balls using Softmax Temperature Scaling (tau = 0.45)
        blue_energies = np.array([get_wuxing_energy(b, is_blue=True) for b in range(1, 17)], dtype=float)
        exp_b = np.exp((blue_energies - np.max(blue_energies)) / tau)
        blue_probs = (exp_b / np.sum(exp_b)).tolist()

        # 3. Meihua Prophecy Construction
        base_prophecy = HEXAGRAM_PROPHECIES.get(
            hex_name,
            f"【周易第{hex_idx+1}卦·{hex_name}】乾坤造化，阴阳相济，金水相涵，气机勃发。",
        )
        prophecy = (
            f"{base_prophecy} 动爻居第{dongyao}爻，变卦感应【{bian_up}下{bian_low}】(用神属{bian_element})，"
            f"互卦【{hu_up}下{hu_low}】(机运属{hu_element})，日支【{day_zhi}】合局共振。"
        )

        metadata = {
            "solar_date": dt.isoformat(),
            "day_ganzhi": day_gz,
            "day_master_element": day_wuxing,
            "zhi_element": zhi_wuxing,
            "hour_wuxing": hour_wuxing,
            "hexagram_name": hex_name,
            "dongyao": dongyao,
            "bian_hexagram": f"{bian_up}下{bian_low}",
            "hu_hexagram": f"{hu_up}下{hu_low}",
            "prophecy_text": prophecy,
        }

        return red_probs, blue_probs, metadata

    @classmethod
    def get_ticket_wuxing_breakdown(cls, reds: List[int], blue: int) -> Dict[str, Any]:
        """
        Calculates element counts and energy distribution for a single ticket.
        """
        counts = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0}
        for r in reds:
            counts[get_ball_wuxing(r)] += 1
        blue_elem = get_ball_wuxing(blue)
        counts[blue_elem] += 1

        total = len(reds) + 1
        percentages = {k: round(v / total * 100, 1) for k, v in counts.items()}

        # Dominant element
        dominant = max(counts.items(), key=lambda x: x[1])[0]

        return {
            "counts": counts,
            "percentages": percentages,
            "dominant_element": dominant,
            "blue_element": blue_elem,
        }
