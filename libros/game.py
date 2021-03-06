import random
import string

from copy import copy
from itertools import cycle
from collections import Counter, defaultdict, namedtuple


ACTION_TAKE_CARD = 0
ACTION_PILE_CARD = 1
ACTION_SHOW_CARD = 2
ACTION_DISCARD_CARD = 3
ACTION_USE_CARD = 4
ACTION_BID_CARD = 5

ACTIONS = [
    ACTION_TAKE_CARD, ACTION_PILE_CARD,
    ACTION_SHOW_CARD, ACTION_DISCARD_CARD,
    ACTION_USE_CARD, ACTION_BID_CARD,
]

COLORS = ('blue', 'brown', 'red', 'orange', 'green')


def deal(players, cards_to_remove=None, gold_to_remove=None):
    assert players in [2, 3, 4]

    if cards_to_remove is None:
        cards_to_remove = {2: 21, 3: 12, 4: 7}.get(players)

    if gold_to_remove is None:
        gold_to_remove = 4 - players

    cards = (
        ('blue',    2, 4),
        ('blue',    3, 3),
        ('blue',    4, 2),
        ('brown',   2, 4),
        ('brown',   3, 3),
        ('brown',   4, 2),
        ('red',     1, 7),
        ('red',     2, 2),
        ('orange',  1, 7),
        ('orange',  2, 2),
        ('green',   1, 7),
        ('green',   2, 2),
        ('change', -2, 2),
        ('change', -1, 2),
        ('change',  2, 2),
        ('change',  1, 2),
        ('change',  0, 1),  # plus or minus
        ('gold',    1, 11 - gold_to_remove),
        ('gold',    2, 11 - gold_to_remove),
        ('gold',    3, 11 - gold_to_remove))
    deck = []
    letters = {}
    for color in COLORS:
        letters[color] = (x for x in string.ascii_uppercase)
    for kind, value, count in cards:
        deck += [{
            'type': kind,
            'value': value,
            'letter': letters.get(kind, cycle([None])).next(),
        } for _ in xrange(count)]
    random.shuffle(deck)

    return deck[cards_to_remove:]


class Game(object):
    def __init__(self):
        self.players = []
        self.players_cycle = []
        self.deck = None
        self.state = 'waiting'
        self.player = None
        self.player_turns_left = 0
        self.pile = []
        self.public = []
        self.discarded = []
        self.actions_taken = Counter()
        self.dice = {color: 3 for color in COLORS}
        self.auction_card = None

    def join(self, player):
        self.players.append(player)
        player.join(self, len(self.players))

    def start(self):
        assert self.player_count in [2, 3, 4]

        self.state = 'start'
        self.player_turns_left = self.turns_per_player
        self.deck = deal(self.player_count)
        self.players_cycle = cycle(self.players)

        self.state = 'next_player'
        self.next_player()

    @property
    def turns_per_player(self):
        # 1 into hand + 1 into pile + (player_count - 1) to the front
        return 2 + self.player_count - 1

    @property
    def player_count(self):
        return len(self.players)

    @property
    def deck_count(self):
        return len(self.deck)

    @property
    def pile_count(self):
        return len(self.pile)

    @property
    def discarded_count(self):
        return len(self.discarded)

    @property
    def public_count(self):
        return len(self.public)

    def next_player(self):
        if self.state == 'next_player':
            self.state = 'turn'
            self.reset_actions()
            self.player = next(self.players_cycle)
            self.player_turns_left = self.turns_per_player
        elif self.state == 'public':
            self.player = next(self.players_cycle)
        elif self.state == 'auction':
            self.reset_actions()
            self.player = next(self.players_cycle)
        else:
            raise ValueError('Incorrect state.')

    @property
    def active_player(self):
        return self.player

    @property
    def turns_left(self):
        return self.player_turns_left

    def turn(self):
        player = self.active_player

        if self.state == 'turn':
            assert self.deck
            assert self.turns_left > 0
            card = self.deck.pop()
            self.player_turns_left -= 1
        elif self.state == 'public':
            card = player.choose_public_card(copy(self.public))
        elif self.state == 'auction':
            if self.auction_card:
                card = self.auction_card
            else:
                card = self.pile.pop()
                card['bid_player'], card['bid_gold'] = (None, 0)
                self.auction_card = card
        else:
            raise ValueError('Incorrect state.')

        return player, card, self.valid_actions(player, card)

    def turn_action(self, player, card, action, change_colors, bid_gold):
        """Handles player action and its influence on the game."""
        action_func = {
            ACTION_PILE_CARD: lambda: self.pile.append(card),
            ACTION_SHOW_CARD: lambda: self.public.append(card),
            ACTION_USE_CARD: lambda: self.use_change_card(card, change_colors),
        }.get(action, lambda: None)

        if self.state == 'public':
            # we're in the public phase so we first remove the card
            self.public.remove(card)

        action_func()
        self.actions_taken[action] += 1

        if self.state == 'auction' and action == ACTION_BID_CARD and bid_gold:
            # the player placed a bid so if it's higher (and not bidding again)
            # we update the card with the new highest bidder
            if bid_gold > card['bid_gold'] and player != card['bid_player']:
                card['bid_player'], card['bid_gold'] = (player, bid_gold)
        elif self.state == 'auction' and action == ACTION_BID_CARD:
            # if current player didn't place the bid, but still is the last
            # card bidder then this card now belongs to him
            if player == card['bid_player']:
                card['bid_won'] = True
        elif self.state == 'auction':
            # action isnt ACTION_BID_CARD which means the player that won
            # the card is doing something else with it
            self.auction_card = None

        if action in (ACTION_DISCARD_CARD, ACTION_USE_CARD):
            # discarding/using a card counts as taking it first as well
            self.actions_taken[ACTION_TAKE_CARD] += 1
            self.discarded.append(card)

    def use_change_card(self, card, colors):
        value = card['value']
        assert card['type'] == 'change'
        assert len(colors) == 0 or len(colors) == max(abs(value), 1)

        if not colors:
            return

        if value == 0:
            value = colors[0] == '+' and 1 or -1
            colors = [colors[0][1:]]
        for color in colors:
            if value < 0:
                self.dice[color] -= 1
            else:
                self.dice[color] += 1

    def turn_complete(self, player, card, action):
        """Handles moving to the next state and advancing player turns."""
        if self.turns_left == 0 and self.public:
            self.state = 'public'
            self.next_player()

        if self.deck_count == 0 and not self.public:
            self.state = 'auction'
            # if the player won the card he still needs to use it
            if 'bid_won' not in card:
                self.next_player()

        if self.state == 'auction' and not self.pile and not self.auction_card:
            self.state = 'end'

        if self.state == 'public' and not self.public:
            # current player finished their turn
            self.state = 'next_player'
            self.next_player()

    def valid_actions(self, player, card):
        """Returns a list of valid actions for the current turn."""
        if self.state == 'public':
            if card['type'] == 'change':
                return [ACTION_DISCARD_CARD, ACTION_USE_CARD]
            return [ACTION_TAKE_CARD]

        if self.state == 'auction' and card['bid_player'] != player:
            return [ACTION_BID_CARD]

        actions = copy(ACTIONS)
        actions.remove(ACTION_DISCARD_CARD)
        actions.remove(ACTION_USE_CARD)
        actions.remove(ACTION_BID_CARD)

        # if we have shown enough cards remove the action
        if (self.state == 'auction' or
                self.actions_taken[ACTION_SHOW_CARD] == self.player_count - 1):
            actions.remove(ACTION_SHOW_CARD)

        if (self.state == 'auction' or
                self.actions_taken[ACTION_PILE_CARD]):
            actions.remove(ACTION_PILE_CARD)

        if self.state != 'auction' and self.actions_taken[ACTION_TAKE_CARD]:
            actions.remove(ACTION_TAKE_CARD)

        if card['type'] == 'change' and ACTION_TAKE_CARD in actions:
            actions.append(ACTION_DISCARD_CARD)
            actions.append(ACTION_USE_CARD)

        return actions

    def reset_actions(self):
        self.actions_taken.clear()

    def winner(self):
        score = namedtuple('Score', ['valueletter', 'player'])
        player_won = defaultdict(lambda: {})
        player_scores = defaultdict(lambda: 0)
        for color in COLORS:
            winner = max([score(player.score_type(color), player)
                          for player in self.players])
            if winner.valueletter.value:
                player_scores[winner.player] += self.dice[color]
                player_won[winner.player][color] = True
        # The rules don't say this but the author says "Those involved in the
        # tie for the win will use the Illuminator category as a tie-breaker;
        # hence, whoever has the highest total value wins, then it goes to
        # tie-breaker card. If none of the tied players have an Illuminator,
        # then it moves down the line to Scribes and so on. This way, everyone
        # knows that Illuminators are slightly more valuable to have."
        return max((score,
                    player.score_type('gold').value,
                    'brown' in player_won[player],
                    'blue' in player_won[player],
                    'green' in player_won[player],
                    'orange' in player_won[player],
                    'red' in player_won[player],
                    player)
                   for player, score in player_scores.iteritems())[7]


class Player(object):
    def __init__(self):
        self.game = None
        self.cards = []
        self.id = None

    def __repr__(self):
        return u'ID: %d, Cards: %d' % (self.id, len(self.cards))

    def join(self, game, number):
        assert not self.game
        self.game = game
        self.id = number

    def choose_public_card(self, cards):
        assert cards
        return cards[0]

    def act(self, card, action=None, change_colors=None, bid_gold=None):
        assert self.game
        assert card

        if action is None:
            action = random.choice(ACTIONS)

        assert action in ACTIONS

        if action == ACTION_USE_CARD and change_colors is None:
            change_colors = []

        if (bid_gold is None and
                action == ACTION_BID_CARD and card['bid_player'] != self):
            # first player bidding will get the card as he will bid the highest
            bid_gold = 1

        if action == ACTION_TAKE_CARD:
            self.cards.append(card)

        self.game.turn_action(
            self, card, action, change_colors=change_colors, bid_gold=bid_gold)
        self.game.turn_complete(self, card, action)

        return action

    def score_type(self, type):
        ValueLetter = namedtuple('ValueLetter', ['value', 'letter'])
        cards = [ValueLetter(card['value'], card['letter'])
                 for card in self.cards if card['type'] == type]
        if not cards:
            return ValueLetter(0, None)
        return ValueLetter(sum(card.value for card in cards),
                           min(card.letter for card in cards))
