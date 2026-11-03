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

        # 1. Score 33 Red Balls
        red_scores = []
        for b in range(1, 34):
            b_wuxing = get_ball_wuxing(b)
            _, mult = cls.calculate_ten_gods_relation(day_gan, b)

            # Hour harmony (Hai Water supports Wood, promotes Water, controlled by Earth)
            if b_wuxing in ("木", "水"):
                mult *= 1.08
            elif b_wuxing == "火":
                mult *= 1.02

            # Jiugong Modulo
            star = JIUGONG_BAGUA[b % 9]
            if star["element"] in (day_wuxing, hour_wuxing):
                mult *= 1.05

            red_scores.append(mult)

        # Normalize Red scores
        r_sum = sum(red_scores)
        red_probs = [s / r_sum for s in red_scores]

        # 2. Score 16 Blue Balls (Blue is deeply connected to Kan Water and Zhen Wood)
        blue_scores = []
        for b in range(1, 17):
            b_wuxing = get_ball_wuxing(b)
            _, mult = cls.calculate_ten_gods_relation(day_gan, b)
            if b_wuxing == "水":
                mult *= 1.15
            elif b_wuxing == "金":  # Metal generates Water
                mult *= 1.12

            blue_scores.append(mult)

        b_sum = sum(blue_scores)
        blue_probs = [s / b_sum for s in blue_scores]

        # 3. Meihua Yishu Hexagram Generation
        # Upper trigram = (Year + Month + Day + Issue_sum) % 8
        try:
            issue_int = sum(int(c) for c in str(issue_no) if c.isdigit())
        except Exception:
            issue_int = 18

        upper_num = (dt.year + dt.month + dt.day) % 8
        lower_num = (dt.year + dt.month + dt.day + 12 + issue_int) % 8  # 12 is Hai hour
        hex_idx = (upper_num * 8 + lower_num) % len(HEXAGRAM_NAMES)
        hex_name = HEXAGRAM_NAMES[hex_idx]
        prophecy = HEXAGRAM_PROPHECIES.get(
            hex_name,
            f"【周易第{hex_idx+1}卦·{hex_name}】乾坤造化，阴阳相济，金水相涵，气机勃发。",
        )

        metadata = {
            "solar_date": dt.isoformat(),
            "day_ganzhi": day_gz,
            "day_master_element": day_wuxing,
            "zhi_element": zhi_wuxing,
            "hour_wuxing": hour_wuxing,
            "hexagram_name": hex_name,
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
