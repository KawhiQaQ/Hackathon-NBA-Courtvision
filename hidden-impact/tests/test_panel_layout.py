import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cloud/api'))
from panel_layout import choose_position, nameplates, overlap

class PanelLayoutTests(unittest.TestCase):
    def test_brief_opening_collision_is_not_outvoted_by_later_quiet_frames(self):
        opening = [((650, 170, 740, 290), 3)]
        later = [((150, 420, 240, 530), 1)]
        self.assertEqual(choose_position([opening] + [later] * 50), (16, 48))

    def test_compact_panel_clears_nameplate_below_it(self):
        samples = [[((258, 214, 480, 243), 3), ((690, 150, 790, 300), 3)]]
        x, y = choose_position(samples, card_width=296, card_height=160)
        self.assertEqual((x, y), (16, 48))
        self.assertEqual(overlap((x,y,x+296,y+160), samples[0][0][0]), 0)

    def test_nameplates_include_stacking_and_ignore_offscreen_people(self):
        people = [dict(trackId=str(i), x=.6, y=.4, w=.05, h=.2) for i in range(3)]
        people[2]['offscreen'] = True
        roles = {str(i): {'displayName': '球员'} for i in range(3)}
        boxes = nameplates(people, roles, 960, 540, lambda text: 160)
        self.assertEqual(len(boxes), 2)
        self.assertEqual(overlap(boxes[0][3], boxes[1][3]), 0)

    def test_label_moves_beside_card_without_moving_player_anchor(self):
        people = [dict(trackId='b', x=.35, y=.2, w=.05, h=.2)]
        obstacle = (16, 48, 312, 208)
        layout = nameplates(people, {'b': {'displayName': '受益队友'}}, 960, 540,
                            lambda text: 200, obstacle)[0]
        self.assertEqual(overlap(layout[3], obstacle), 0)
        self.assertAlmostEqual(layout[2], .375 * 960)

if __name__ == '__main__': unittest.main()
