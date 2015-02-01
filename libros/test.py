from unittest import TestCase

from libros.game import deal, Game, Player, ACTIONS


class TestGame(TestCase):
    def test_deal(self):
        self.assertEqual(len(deal(4)), 80)
        self.assertEqual(len(deal(3)), 72)
        self.assertEqual(len(deal(2)), 60)

    def test_join(self):
        player1 = Player()
        player2 = Player()
        game = Game()
        game.join(player1)
        self.assertEqual(game.state, 'waiting')
        self.assertEqual(game.player_count, 1)
        game.join(player2)
        self.assertEqual(game.state, 'waiting')
        self.assertEqual(game.player_count, 2)
        game.start()
        self.assertEqual(game.state, 'place')

    def _player_turn(self, game):
        active_player = game.active_player

        player, card = game.turn()
        choice = player.act(card)

        self.assertIn(choice, ACTIONS)
        self.assertEqual(player, active_player)

        return player, card, choice

    def test_game(self):
        player1 = Player()
        player2 = Player()
        game = Game()
        game.join(player1)
        game.join(player2)
        game.start()

        self.assertEqual(game.state, 'place')
        self.assertEqual(game.player_count, 2)

        player, card, choice = self._player_turn(game)
