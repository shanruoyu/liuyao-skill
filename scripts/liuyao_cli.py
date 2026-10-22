#!/usr/bin/env python3
"""Three-coin Liuyao charting. Lines and coin groups are ALWAYS bottom-up."""
from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RULESET = "liuyao-najia-v1"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEMS = "甲乙丙丁戊己庚辛壬癸"
ELEMENT = dict(zip(BRANCHES, ["水","土","木","木","土","火","火","土","金","金","土","水"]))
GENERATES = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
CONTROLS = {"木":"土","土":"水","水":"火","火":"金","金":"木"}
# All bit strings below run from the lowest line to the highest.
TRIGRAMS = {"111":("乾","金"),"110":("兑","金"),"101":("离","火"),"100":("震","木"),
            "011":("巽","木"),"010":("坎","水"),"001":("艮","土"),"000":("坤","土")}
PALACE_NAMES = {
"乾":["乾为天","天风姤","天山遁","天地否","风地观","山地剥","火地晋","火天大有"],
"兑":["兑为泽","泽水困","泽地萃","泽山咸","水山蹇","地山谦","雷山小过","雷泽归妹"],
"离":["离为火","火山旅","火风鼎","火水未济","山水蒙","风水涣","天水讼","天火同人"],
"震":["震为雷","雷地豫","雷水解","雷风恒","地风升","水风井","泽风大过","泽雷随"],
"巽":["巽为风","风天小畜","风火家人","风雷益","天雷无妄","火雷噬嗑","山雷颐","山风蛊"],
"坎":["坎为水","水泽节","水雷屯","水火既济","泽火革","雷火丰","地火明夷","地水师"],
"艮":["艮为山","山火贲","山天大畜","山泽损","火泽睽","天泽履","风泽中孚","风山渐"],
"坤":["坤为地","地雷复","地泽临","地天泰","雷天大壮","泽天夬","水天需","水地比"],
}
MASKS = [0,1,3,7,15,31,23,16]
STAGES = ["本宫","一世","二世","三世","四世","五世","游魂","归魂"]
SHI = [6,1,2,3,4,5,4,3]
# Inner 1/2/3 and outer 4/5/6, both bottom-up. 增删卜易 chapters 4-7.
NAJIA = {
"乾":(("甲","子寅辰"),("壬","午申戌")),
"兑":(("丁","巳卯丑"),("丁","亥酉未")),
"离":(("己","卯丑亥"),("己","酉未巳")),
"震":(("庚","子寅辰"),("庚","午申戌")),
"巽":(("辛","丑亥酉"),("辛","未巳卯")),
"坎":(("戊","寅辰午"),("戊","申戌子")),
"艮":(("丙","辰午申"),("丙","戌子寅")),
"坤":(("乙","未巳卯"),("癸","丑亥酉")),
}
SPIRITS = ["青龙","朱雀","勾陈","螣蛇","白虎","玄武"]
SPIRIT_START = dict(zip(STEMS, [0,0,1,1,2,3,4,4,5,5]))
KINDS = ["父母","兄弟","子孙","妻财","官鬼"]
TOPICS = {
"career_position":("官鬼",["父母"],"职位、录用、晋升"),
"payment":("妻财",[],"工资、报酬、回款"),
"wealth":("妻财",["子孙"],"收益与财物"),
"exam_selection":("官鬼",["父母"],"竞争录取、功名资格"),
"exam_paper":("父母",["官鬼"],"试卷、文章、考试分数"),
"document":("父母",[],"合同、证书、手续、文书"),
"relationship":("世应",[],"本人和指定对方的互动"),
"relative":("人物",[],"指定亲属本人"),
"lost_money":("妻财",[],"钱财、货物本体"),
"lost_document":("父母",[],"证件、文书、衣物、车辆等"),
"pet":("子孙",[],"宠物本人或寻找宠物"),
"health":("人物",["官鬼","子孙"],"仅列传统人物、病事与医药象义"),
}
# Conservative suggestions only; these patterns are NOT a semantic oracle.
PATTERNS = {
"career_position":r"求职|应聘|面试|升职|晋升|任职|录用|岗位|offer",
"payment":r"工资|薪资|薪水|奖金|报酬|回款|尾款|欠款|到账",
"wealth":r"求财|收益|盈利|利润|赚钱",
"exam_selection":r"录取|入围|考上|上岸",
"exam_paper":r"试卷|论文|答辩|考试成绩|考试分数",
"document":r"合同|证书|证件|批文|手续|签证|房产证",
"relationship":r"恋爱|复合|结婚|分手|感情",
"pet":r"宠物|猫咪|小猫|狗狗|小狗",
"health":r"病情|疾病|治疗|吃药|身体",
}
RELATIONS = {"self":"世","parent":"父母","sibling":"兄弟","child":"子孙","partner":"应"}
ALLOWED = {"coins","question","topic","subject_relation","cast_time","day_boundary","ruleset"}

def bits_number(bits):
    return sum(bit << i for i, bit in enumerate(bits))

HEXAGRAMS = {}
for tri_bits, (palace, element) in TRIGRAMS.items():
    base = bits_number([int(x) for x in tri_bits * 2])
    for index, mask in enumerate(MASKS):
        code = base ^ mask
        if code in HEXAGRAMS:
            raise RuntimeError("Eight-palace table overlaps")
        HEXAGRAMS[code] = {"name":PALACE_NAMES[palace][index],"palace":palace,
            "palace_element":element,"palace_stage":STAGES[index],
            "shi_position":SHI[index],"ying_position":(SHI[index]+2)%6+1,
            "palace_pure_bits":[int(x) for x in tri_bits * 2]}
assert len(HEXAGRAMS) == 64

def kinship(palace_element, branch):
    element = ELEMENT[branch]
    if element == palace_element: return "兄弟"
    if GENERATES[element] == palace_element: return "父母"
    if GENERATES[palace_element] == element: return "子孙"
    if CONTROLS[palace_element] == element: return "妻财"
    return "官鬼"

def hex_meta(bits):
    info = dict(HEXAGRAMS[bits_number(bits)])
    info["bits_bottom_up"] = "".join(map(str,bits))
    info["lower_trigram"] = TRIGRAMS["".join(map(str,bits[:3]))][0]
    info["upper_trigram"] = TRIGRAMS["".join(map(str,bits[3:]))][0]
    return info

def decorate(bits, reference_element):
    result = []
    for start, section in [(0,0),(3,1)]:
        name = TRIGRAMS["".join(map(str,bits[start:start+3]))][0]
        stem, branches = NAJIA[name][section]
        for offset, branch in enumerate(branches):
            result.append({"position":start+offset+1,"yin_yang":bits[start+offset],
                "stem":stem,"branch":branch,"ganzhi":stem+branch,
                "element":ELEMENT[branch],"kinship":kinship(reference_element,branch)})
    return result

def calendar_info(payload):
    stamp = payload.get("cast_time")
    boundary = payload.get("day_boundary","midnight")
    if boundary not in ("midnight","zi_start"):
        raise ValueError("day_boundary must be midnight or zi_start")
    if stamp is None:
        return {"status":"missing","day_boundary":boundary,"data":None}
    if not isinstance(stamp,str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)",stamp) is None:
        raise ValueError("cast_time must include date, hour, minute and UTC offset; seconds are optional")
    try:
        original = datetime.fromisoformat(stamp.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("cast_time needs a valid complete date/time and UTC offset") from exc
    if original.tzinfo is None or "T" not in stamp:
        raise ValueError("cast_time needs T and explicit UTC offset; date-only/naive times are not filled")
    civil = original.astimezone(timezone(timedelta(hours=8)))
    try:
        from lunar_python import Solar
    except ImportError as exc:
        raise RuntimeError("Calendar requested: install scripts/requirements.txt (lunar_python)") from exc
    lunar = Solar.fromYmdHms(civil.year,civil.month,civil.day,civil.hour,civil.minute,civil.second).getLunar()
    day = lunar.getDayInGanZhiExact() if boundary == "zi_start" else lunar.getDayInGanZhiExact2()
    gan_index, branch_index = STEMS.index(day[0]), BRANCHES.index(day[1])
    xun_start = (branch_index-gan_index)%12
    return {"status":"exact","day_boundary":boundary,"data":{
        "original_timestamp":stamp,"calendar_timezone":"UTC+08:00",
        "beijing_timestamp":civil.isoformat(),
        "month_ganzhi":lunar.getMonthInGanZhiExact(),
        "month_branch":lunar.getMonthZhiExact(),"day_ganzhi":day,
        "xun_kong":[BRANCHES[(xun_start+10)%12],BRANCHES[(xun_start+11)%12]],
        "six_spirits_bottom_up":[SPIRITS[(SPIRIT_START[day[0]]+i)%6] for i in range(6)],
        "month_rule":"十二节的实际交接瞬间；不是农历初一"}}

def validate(payload):
    if not isinstance(payload,dict):
        raise ValueError("Input must be a JSON object")
    unknown = set(payload)-ALLOWED
    if unknown:
        raise ValueError("Unsupported fields: "+", ".join(sorted(unknown))+
                         ". Moving lines are derived from coins, never supplied separately.")
    if payload.get("ruleset",RULESET) != RULESET:
        raise ValueError("Only ruleset="+RULESET+" is implemented")
    coins = payload.get("coins")
    if not isinstance(coins,list) or len(coins) != 6:
        raise ValueError("coins must contain exactly six strings, first cast = bottom line")
    if any(not isinstance(x,str) or re.fullmatch(r"[01]{3}",x) is None for x in coins):
        raise ValueError("Each cast must be a three-character binary STRING, e.g. '001'; numbers are not padded")
    question = payload.get("question","")
    if not isinstance(question,str):
        raise ValueError("question must be a string")
    if payload.get("topic") is not None and (not isinstance(payload["topic"],str) or payload["topic"] not in TOPICS):
        raise ValueError("Unknown topic; allowed: "+", ".join(TOPICS))
    if not isinstance(payload.get("subject_relation","self"),str) or payload.get("subject_relation","self") not in set(RELATIONS)|{"other"}:
        raise ValueError("Unknown subject_relation")
    return coins, question.strip()

def compact(line, source):
    return {k:line[k] for k in ("position","ganzhi","element","kinship")} | {
        "source":source,"moving":line.get("moving",False)}

def selector(kind, chart, calendar):
    if kind in ("世","应"):
        position = chart["primary"][("shi_position" if kind=="世" else "ying_position")]
        candidates = [compact(chart["lines"][position-1],"visible")]
        return {"kind":kind,"status":"unique_visible","selected_line":position,
                "candidates":candidates,"hidden_candidates":[],"changed_candidates":[],"external_candidates":[]}
    visible = [compact(x,"visible") for x in chart["lines"] if x["kinship"] == kind]
    hidden = [x for x in chart["hidden_lines"] if x["kinship"] == kind]
    changed = [compact(x,"changed") for x in chart["changed_lines"]
               if x["is_active_counterpart"] and x["kinship"] == kind]
    external = []
    if calendar["data"]:
        for source, branch in [("month",calendar["data"]["month_branch"]),
                               ("day",calendar["data"]["day_ganzhi"][1])]:
            if kinship(chart["primary"]["palace_element"],branch)==kind:
                external.append({"source":source,"branch":branch,"kinship":kind})
    status = ("unique_visible" if len(visible)==1 else "multiple_visible_review" if visible
              else "hidden_or_external_review" if hidden or external or changed else "absent")
    return {"kind":kind,"status":status,
            "selected_line":visible[0]["position"] if len(visible)==1 else None,
            "candidates":visible,"hidden_candidates":hidden,
            "changed_candidates":changed,"external_candidates":external}

def choose_yongshen(payload, question, chart, calendar):
    relation = payload.get("subject_relation","self")
    relation_confirmed = "subject_relation" in payload
    person = selector(RELATIONS[relation],chart,calendar) if relation_confirmed and relation in RELATIONS else None
    actor = {"subject_relation":relation if relation_confirmed else None,
             "source":"explicit" if relation_confirmed else "unconfirmed",
             "person_selector":person}
    if not question:
        return {"status":"missing_question","actor":actor,"topic":None,
                "primary":[],"auxiliary":[],"clarifications":["请说明一个具体问题、涉及谁和所问结果。"]}
    hits = [topic for topic, pattern in PATTERNS.items() if re.search(pattern,question,re.I)]
    warnings = []
    topic = payload.get("topic")
    if topic:
        source = "explicit_topic"
        if hits and topic not in hits:
            warnings.append("指定topic与关键词候选不一致，请核对问题目标；未擅自改用神。")
    elif len(hits)==1:
        return {"status":"suggestion_only","actor":actor,"topic":None,
                "topic_source":"keyword_suggestion","topic_candidates":hits,
                "primary":[],"auxiliary":[],
                "clarifications":["关键词仅提供候选；请根据完整问题明确涉及谁和主要结果，再传topic与subject_relation。"]}
    else:
        return {"status":"clarification_required","actor":actor,"topic":None,
                "topic_candidates":hits,"primary":[],"auxiliary":[],
                "clarifications":["请明确主要结果：职位、钱款、文书、录取、特定关系，或其他事项；多个目标须分别说明。"]}
    if not relation_confirmed:
        return {"status":"clarification_required","actor":actor,"topic":topic,
                "topic_source":source,"primary":[],"auxiliary":[],
                "clarifications":["请根据用户原话明确事情涉及谁，设置subject_relation；不默认把第三人设为本人。"]}
    if relation == "other" or (relation=="self" and re.search(r"妈|母亲|爸|父亲|姐|妹|哥|弟|儿子|女儿|替|代问",question)) or (relation=="self" and topic!="relationship" and re.search(r"他(?:的|能|会|是否)|她|朋友|同事|丈夫|妻子|男友|女友",question)):
        return {"status":"clarification_required","actor":actor,"topic":topic,
                "topic_source":source,"primary":[],"auxiliary":[],
                "clarifications":["请明确事情涉及谁，设置subject_relation；代问要保留人物与事项两层。"]}
    if topic=="relationship" and not re.search(r"对方|伴侣|对象|男友|女友|丈夫|妻子|爱人|前任|我们|我和",question):
        return {"status":"clarification_required","actor":actor,"topic":topic,
                "primary":[],"auxiliary":[],"clarifications":["请明确是否有指定对方，以及所问的是复合、联系、相处还是承诺；v1世应模式不猜泛泛姻缘。"]}
    primary_kind, auxiliaries, description = TOPICS[topic]
    if primary_kind=="世应":
        if relation not in ("self","partner"):
            return {"status":"clarification_required","actor":actor,"topic":topic,
                    "primary":[],"auxiliary":[],"clarifications":["代问他人的关系，须先明确摇卦者、双方身份及角色口径。"]}
        primary = [selector("世",chart,calendar),selector("应",chart,calendar)]
    elif primary_kind=="人物":
        primary = [person] if person else []
    else:
        primary = [selector(primary_kind,chart,calendar)]
    if topic=="health":
        warnings.append("此项仅列传统人物/病事/医药象义；不据卦输出诊断、寿夭、停药或疗效结论。")
    if topic=="relative" and relation=="self":
        return {"status":"clarification_required","actor":actor,"topic":topic,
                "primary":[],"auxiliary":[],"clarifications":["请明确所问亲属与自己的关系。"]}
    return {"status":"classified","actor":actor,"topic":topic,"topic_source":source,
            "topic_description":description,"topic_candidates":hits,
            "primary":primary,"auxiliary":[selector(k,chart,calendar) for k in auxiliaries],
            "warnings":warnings,
            "selection_note":"选定六亲类别不等于断成败；多现保留全部，伏神/日月/化出分别标源。"}

def build_output(payload):
    coins, question = validate(payload)
    scores = [6+x.count("1") for x in coins]
    bits = [x%2 for x in scores]
    moving = [i+1 for i,x in enumerate(scores) if x in (6,9)]
    changed_bits = [1-x if i+1 in moving else x for i,x in enumerate(bits)]
    primary, changed = hex_meta(bits), hex_meta(changed_bits)
    lines = decorate(bits,primary["palace_element"])
    changed_lines = decorate(changed_bits,primary["palace_element"])
    states = {6:"老阴",7:"少阳",8:"少阴",9:"老阳"}
    calendar = calendar_info(payload)
    for i,line in enumerate(lines):
        line.update(raw_coins=coins[i],coin_score=scores[i],state=states[scores[i]],
                    moving=i+1 in moving,changed_yin_yang=changed_bits[i],
                    is_shi=i+1==primary["shi_position"],is_ying=i+1==primary["ying_position"],
                    six_spirit=None,is_xun_kong=None,is_month_break=None)
        changed_lines[i]["is_active_counterpart"] = i+1 in moving
        if calendar["data"]:
            data = calendar["data"]
            line.update(six_spirit=data["six_spirits_bottom_up"][i],
                        is_xun_kong=line["branch"] in data["xun_kong"],
                        is_month_break=(BRANCHES.index(line["branch"])-BRANCHES.index(data["month_branch"]))%12==6)
    present = {x["kinship"] for x in lines}
    hidden = []
    for line in decorate(primary["palace_pure_bits"],primary["palace_element"]):
        if line["kinship"] not in present:
            hidden.append(compact(line,"hidden") | {"flying_line":compact(lines[line["position"]-1],"visible"),
                "rule":"仅补本卦缺失六亲，从本宫纯卦同位取伏"})
    chart = {"primary":primary,"changed":changed,"change_status":"changed" if moving else "static_same_as_primary",
             "moving_positions":moving,"lines":lines,"changed_lines":changed_lines,
             "changed_kinship_reference_palace":primary["palace"],
             "hidden_lines":hidden}
    yongshen = choose_yongshen(payload,question,chart,calendar)
    limitations = ["脚本不输出吉凶概率或必然事件；不自动判暗动、旺衰、三合化局、应期。"]
    if not calendar["data"]:
        limitations.append("未提供起卦时刻：六神、旬空、月破为null；不可补当前日期或出生日期。")
    if not moving:
        limitations.append("此卦明确全静；变卦仅为同卦对照，没有主动变爻。")
    return {"ruleset":{"id":RULESET,"coin_rule":"0=阴面2分，1=阳面3分；每摇三枚，合计6/7/8/9",
                     "line_order":"bottom_up","calendar_timezone":"UTC+08:00",
                     "day_boundary":calendar["day_boundary"],
                     "changed_kinship":"always reference original palace element"},
            "input":{"coins":coins,"question":question},"chart":chart,"calendar":calendar,
            "yongshen":yongshen,"limitations":limitations}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",default="-",help="JSON file or - for stdin")
    parser.add_argument("--output",default="-",help="JSON file or - for stdout")
    args = parser.parse_args()
    if hasattr(sys.stdout,"reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        raw = sys.stdin.read() if args.input=="-" else Path(args.input).read_text(encoding="utf-8-sig")
        result, code = build_output(json.loads(raw)), 0
    except Exception as exc:
        result, code = {"error":type(exc).__name__,"message":str(exc)}, 2
    text = json.dumps(result,ensure_ascii=False,indent=2)
    if args.output=="-":
        print(text)
    else:
        output = Path(args.output)
        if args.input!="-" and output.resolve()==Path(args.input).resolve():
            raise SystemExit("Input and output paths must differ")
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(text+"\n",encoding="utf-8")
    return code

if __name__=="__main__":
    raise SystemExit(main())
