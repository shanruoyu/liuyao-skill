"""Observable invariants and classical chart examples; no prediction accuracy claims."""
import itertools
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import liuyao_cli as l

def chart(coins, **kwargs):
    return l.build_output({"coins":coins,**kwargs})

def from_values(values, **kwargs):
    enc = {6:"000",7:"001",8:"011",9:"111"}
    return chart([enc[x] for x in values],**kwargs)

class Charts(unittest.TestCase):
    def test_user_example(self):
        out=chart(["000","001","011","111","010","101"])
        c=out["chart"]
        self.assertEqual([x["coin_score"] for x in c["lines"]],[6,7,8,9,7,8])
        self.assertEqual(c["primary"]["name"],"泽水困")
        self.assertEqual(c["primary"]["bits_bottom_up"],"010110")
        self.assertEqual(c["moving_positions"],[1,4])
        self.assertEqual(c["changed"]["name"],"水泽节")
        self.assertEqual(c["changed"]["bits_bottom_up"],"110010")
        self.assertEqual(c["changed_kinship_reference_palace"],"兑")
        self.assertEqual(c["changed_lines"][0]["kinship"],"官鬼")
        self.assertEqual(c["changed_lines"][3]["kinship"],"兄弟")

    def test_permutations(self):
        a=chart(["000","001","011","111","010","101"])["chart"]
        b=chart(["000","100","110","111","001","011"])["chart"]
        self.assertEqual(a["primary"],b["primary"])
        self.assertEqual(a["changed"],b["changed"])
        self.assertEqual(a["moving_positions"],b["moving_positions"])

    def test_all_moving_and_static(self):
        self.assertEqual(chart(["000"]*6)["chart"]["changed"]["name"],"乾为天")
        self.assertEqual(chart(["111"]*6)["chart"]["changed"]["name"],"坤为地")
        c=chart(["001","100","010","011","110","101"])["chart"]
        self.assertEqual(c["primary"]["name"],"地天泰")
        self.assertEqual(c["change_status"],"static_same_as_primary")
        self.assertEqual(c["moving_positions"],[])

    def test_classical_xu_song(self):
        # 增删卜易 动变章：需变讼，变爻六亲仍按坤宫土。
        c=from_values([9,7,9,6,7,6])["chart"]
        self.assertEqual((c["primary"]["name"],c["changed"]["name"]),("水天需","天水讼"))
        self.assertEqual((c["primary"]["palace"],c["primary"]["palace_stage"]),( "坤","游魂"))
        self.assertEqual((c["primary"]["shi_position"],c["primary"]["ying_position"]),(4,1))
        self.assertEqual([x["ganzhi"] for x in c["changed_lines"]],["戊寅","戊辰","戊午","壬午","壬申","壬戌"])
        self.assertEqual([c["changed_lines"][i-1]["kinship"] for i in [1,3,4,6]],
                         ["官鬼","父母","父母","兄弟"])

    def test_classical_guai_gou(self):
        c=from_values([9,7,7,7,7,6])["chart"]
        self.assertEqual((c["primary"]["name"],c["changed"]["name"]),("泽天夬","天风姤"))
        self.assertEqual((c["primary"]["shi_position"],c["primary"]["ying_position"]),(5,2))
        self.assertEqual(c["changed_lines"][0]["kinship"],"兄弟")
        self.assertEqual(c["changed_lines"][5]["kinship"],"兄弟")

    def test_hidden_stars(self):
        c=from_values([7,8,7,8,8,7])["chart"]
        self.assertEqual(c["primary"]["name"],"山火贲")
        self.assertEqual([(x["position"],x["ganzhi"],x["kinship"]) for x in c["hidden_lines"]],
                         [(2,"丙午","父母"),(3,"丙申","子孙")])

    def test_all_4096_polarity_motion_combinations(self):
        seen=set()
        for values in itertools.product([6,7,8,9],repeat=6):
            c=from_values(values)["chart"]
            a,b=c["primary"],c["changed"]
            seen.add(a["bits_bottom_up"])
            self.assertEqual(len(c["lines"]),6)
            self.assertEqual((a["shi_position"]-a["ying_position"])%6,3)
            self.assertEqual([i+1 for i,(x,y) in enumerate(zip(a["bits_bottom_up"],b["bits_bottom_up"])) if x!=y],
                             c["moving_positions"])
            self.assertEqual(sum(x["is_active_counterpart"] for x in c["changed_lines"]),len(c["moving_positions"]))
            for line in c["lines"]:
                self.assertEqual(line["kinship"],l.kinship(a["palace_element"],line["branch"]))
        self.assertEqual(len(seen),64)

    def test_input_rejection(self):
        for coins in [[],["001"]*5,["001"]*7,[1]*6,[True]*6,["01"]*6,["0000"]*6,["00x"]*6]:
            with self.subTest(coins=coins),self.assertRaises(ValueError):
                chart(coins)
        with self.assertRaises(ValueError):
            chart(["001"]*6,moving_lines=[1])
        with self.assertRaises(ValueError):
            chart(["001"]*6,ruleset="anything")
        with self.assertRaises(ValueError):
            chart(["001"]*6,cast_time="2026-02-04")

    def test_partial_and_topic_ambiguity(self):
        out=chart(["001"]*6,question="工作怎么样")
        self.assertEqual(out["calendar"]["status"],"missing")
        self.assertTrue(all(x["six_spirit"] is None for x in out["chart"]["lines"]))
        self.assertEqual(out["yongshen"]["status"],"clarification_required")
        out=chart(["001"]*6,question="面试能通过吗，工资能涨吗？")
        self.assertEqual(out["yongshen"]["status"],"clarification_required")

    def test_unspecified_relationship_and_third_party(self):
        self.assertNotEqual(chart(["001"]*6,question="我的感情怎么样")["yongshen"]["status"],"classified")
        self.assertNotEqual(chart(["001"]*6,question="他是否会被录用")["yongshen"]["status"],"classified")
        self.assertNotEqual(chart(["001"]*6,question="我妈这次应聘能否被录用")["yongshen"]["status"],"classified")
        with self.assertRaises(ValueError):
            chart(["001"]*6,cast_time="2026-02-04T04+08:00")
        with self.assertRaises(ValueError):
            chart(["001"]*6,cast_time="2026-02-04T04:30+08:99")

    def test_role_and_topic_layers(self):
        out=chart(["001"]*6,question="替母亲问是否会被录用",topic="career_position",subject_relation="parent")
        y=out["yongshen"]
        self.assertEqual(y["status"],"classified")
        self.assertEqual(y["actor"]["person_selector"]["kind"],"父母")
        self.assertEqual(y["primary"][0]["kind"],"官鬼")
        rel=chart(["001"]*6,question="我和对方能复合吗",topic="relationship",subject_relation="self")["yongshen"]
        self.assertEqual([x["kind"] for x in rel["primary"]],["世","应"])

    def test_keyword_suggestions_do_not_assign_actor(self):
        y=chart(["001"]*6,question="我同事这次应聘能否被录用")["yongshen"]
        self.assertEqual(y["status"],"suggestion_only")
        self.assertIsNone(y["actor"]["person_selector"])
        y=chart(["001"]*6,question="张三这次应聘能否被录用",topic="career_position")["yongshen"]
        self.assertEqual(y["status"],"clarification_required")
        self.assertIsNone(y["actor"]["subject_relation"])

    def test_multiple_candidates_are_not_silently_ranked(self):
        y=chart(["001"]*6,question="我的合同手续能办好吗",topic="document",subject_relation="self")["yongshen"]["primary"][0]
        self.assertEqual(y["status"],"multiple_visible_review")
        self.assertEqual(len(y["candidates"]),2)
        self.assertIsNone(y["selected_line"])

try:
    import lunar_python
    HAS_CALENDAR=True
except ImportError:
    HAS_CALENDAR=False

@unittest.skipUnless(HAS_CALENDAR,"lunar_python not installed")
class Calendar(unittest.TestCase):
    def test_equivalent_offsets(self):
        a=chart(["001"]*6,cast_time="2026-02-04T03:30:00+08:00")["calendar"]["data"]
        b=chart(["001"]*6,cast_time="2026-02-03T14:30:00-05:00")["calendar"]["data"]
        self.assertEqual(a["beijing_timestamp"],b["beijing_timestamp"])
        self.assertEqual(a["month_ganzhi"],b["month_ganzhi"])
        self.assertEqual(a["day_ganzhi"],b["day_ganzhi"])

    def test_lichun_actual_boundary(self):
        # HKO 2026 almanac: 立春 2/4 04:02 北京时间。
        before=chart(["001"]*6,cast_time="2026-02-04T03:30:00+08:00")["calendar"]["data"]
        after=chart(["001"]*6,cast_time="2026-02-04T04:30:00+08:00")["calendar"]["data"]
        self.assertEqual((before["month_branch"],after["month_branch"]),("丑","寅"))

    def test_zi_boundary(self):
        a=chart(["001"]*6,cast_time="2026-10-21T23:30:00+08:00",day_boundary="midnight")["calendar"]["data"]
        b=chart(["001"]*6,cast_time="2026-10-21T23:30:00+08:00",day_boundary="zi_start")["calendar"]["data"]
        self.assertNotEqual(a["day_ganzhi"],b["day_ganzhi"])
        self.assertNotEqual(a["six_spirits_bottom_up"],b["six_spirits_bottom_up"])

if __name__=="__main__":
    unittest.main()
