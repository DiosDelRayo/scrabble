import argparse
from typing import List, Tuple, Optional, Dict, Union
from random import choice, shuffle, randrange
from hashlib import sha256
from math import log2
from pathlib import Path
from bip39 import encode_bytes
from nacl import pwhash, secret, utils
from binascii import hexlify, unhexlify
from re import match
from functools import lru_cache
from zlib import compress


GRID = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
PLACEMENT_PATTERN = '^[0-9A-Za-z]{2}[\|\-][A-Za-z]+$'
SALT = b'SCRABBLESEEDSKEY'  # TODO: change to dynamic SALT, see later comment

class Board:

    def __init__(self, width: Optional[int] = None, height: Optional[int] = None, word_list: Union[str, Path, None] = None):
        self.encrypted_bytes: Optional[bytes] = None
        self.word_list: List[str] = []
        self.load_word_list(word_list)
        self.width: int = width or 15
        self.height: int = height or 15
        self.password: Optional[str] = None
        self.placements: List[Tuple[bool, str, str, str]] = []
        self.letters: int
        self.init_board()

    def set_password(self, password: Optional[str] = None):
        self.password = password
        self.encrypted_bytes = None

    def add_placement(self, horizontal: bool, x: int, y: int, word: str):
        self.letters += len(word)
        self.placements.append((horizontal, GRID[x], GRID[y], word))
        self.encrypted_bytes = None

    def decode_placement(self, placement: Tuple[bool, str, str, str]) -> Tuple[bool, int, int, str]:
        return (placement[0], GRID.find(placement[1]), GRID.find(placement[2]), placement[3])

    def decode_placement_string(self, placement: str) -> Tuple[bool, int, int, str]:
        return self.decode_placement((placement[2]=='-', placement[0], placement[1], placement[3:]))

    def is_out_of_board(self, horizontal: bool, x: int, y: int, word:str) -> bool:
        if x >= self.width or y >= self.height:
            return True
        if horizontal and x + len(word) > self.width:
            return True
        if not horizontal and y + len(word) > self.height:
            return True
        return False

    def is_direct_parallel_to_other_placements(self, horizontal: bool, x: int, y: int, word: str) -> bool:
        for placement in self.placements:
            _horizontal, _x, _y, _word = self.decode_placement(placement)
            if horizontal != _horizontal:  # can not be parallel, because of different alignment
                continue
            if not horizontal and x != (_x + 1) and x != (_x - 1):  # is not a direct neighbor
                continue
            if horizontal and y != (_y + 1) and y != (_y - 1):  # is not a direct neighbor
                continue
            if horizontal and len(set([__y for __y in range(y, y + len(word))]).intersection(set([___y for ___y in range(_y, _y + len(_word))]))):
                return True
            if not horizontal and len(set([__x for __x in range(x, x + len(word))]).intersection(set([__x for __x in range(_x, _x + len(_word))]))):
                return True
        return False

    def is_on_end_of_other_placement(self, horizontal: bool, x: int, y: int, word: str) -> bool:
        for placement in self.placements:
            _horizontal, _x, _y, _word = self.decode_placement(placement)
            if _horizontal:
                _x = _x + len(_word)
            else:
                _y = _y + len(_word)
            if (_horizontal and _x >= (self.width - 1)) or (not _horizontal and _y >= (self.height - 1)):
                return False
            if horizontal and _y == y and _x in range(x, x + len(word)):
                return True
            if not horizontal and _x == x and _y in range(y, y + len(word)):
                return True
        return False

    def is_in_front_of_other_placement(self, horizontal: bool, x: int, y: int, word: str) -> bool:
        for placement in self.placements:
            _horizontal, _x, _y, _word = self.decode_placement(placement)
            if _horizontal:
                _x = _x - 1
            else:
                _y = _y - 1
            if (not _horizontal and _y < 0) or (horizontal and _x < 0):
                return False
            if horizontal and _y == y and _x in range(x, x + len(word)):
                return True
            if not horizontal and _x == x and _y in range(y, y + len(word)):
                return True
        return False

    def has_another_seed_on_start(self, horizontal: bool, x: int, y: int, word: str) -> bool:
        if horizontal:
            x -= 1
        else:
            y -= 1
        if (horizontal and x < 0) or (not horizontal and y < 0):
            return False
        return self.board[y][x] != ' '

    def has_another_seed_on_end(self, horizontal: bool, x: int, y: int, word: str) -> bool:
        if horizontal:
            x = x + len(word)
        else:
            y = y + len(word)
        if (horizontal and x >= (self.width - 1)) or (not horizontal and y >= (self.height - 1)):
            return False
        return self.board[y][x] != ' '

    def place_horizontal(self, x: int, y: int, word: str) -> bool:
        if self.is_out_of_board(True, x, y, word):
            return False
        if self.is_direct_parallel_to_other_placements(True, x, y, word):
            return False
        if self.is_in_front_of_other_placement(True, x ,y, word):
            return False
        if self.is_on_end_of_other_placement(True, x, y, word):
            return False
        if self.has_another_seed_on_start(True, x, y, word):
            return False
        if self.has_another_seed_on_end(True, x, y, word):
            return False
        if x + len(word) > self.width:
            return False
        for i in range(x, x + len(word)):
            if self.board[y][i] != ' ' and self.board[y][i] != word[i - x]:
                return False
        for i in range(x, x + len(word)):
            self.board[y][i] = word[i - x]
        self.add_placement(True, x, y, word)
        return True

    def place_vertical(self, x: int, y: int, word: str) -> bool:
        if self.is_out_of_board(False, x, y, word):
            return False
        if self.is_direct_parallel_to_other_placements(False, x, y, word):
            return False
        if self.is_in_front_of_other_placement(False, x ,y, word):
            return False
        if self.is_on_end_of_other_placement(False, x, y, word):
            return False
        if self.has_another_seed_on_start(False, x, y, word):
            return False
        if self.has_another_seed_on_end(False, x, y, word):
            return False
        # if y + len(word) > self.size:
        if y + len(word) > self.height:
            return False
        for i in range(y, y + len(word)):
            if self.board[i][x] != ' ' and self.board[i][x] != word[i - y]:
                return False
        for i in range(y, y + len(word)):
            self.board[i][x] = word[i - y]
        self.add_placement(False, x, y, word)
        return True

    def place(self, word: str) -> bool:
        if choice([True, False]):  # place horizontal
            possible_y = [_y for _y in range(0, self.height - len(word) + 1)]
            shuffle(possible_y)
            possible_x = [_x for _x in range(0, self.width)]
            shuffle(possible_x)
            for y in possible_y:
                for x in possible_x:
                    if self.place_horizontal(x, y, word):
                        return True
        else:  # place vertical
            possible_x = [_x for _x in range(0, self.width - len(word) + 1)]
            shuffle(possible_x)
            possible_y = [_y for _y in range(0, self.height)]
            shuffle(possible_y)
            for y in possible_y:
                for x in possible_x:
                    if self.place_vertical(x, y, word):
                        return True
        return False

    def generate(self, min_words: Optional[int] = 3, min_letters: Optional[int] = 30):
        if min_words:
            for i in range(0, min_words):
                while not self.place(choice(self.word_list)):
                    pass
        if min_letters:
            while board.letters < min_letters:
                while not self.place(choice(self.word_list)):
                    pass

    def init_board(self):
        placements = self.placements
        self.board = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        self.placements = []
        self.letters = 0
        self.password = None
        for placement in placements:
            horizontal, x, y, word = self.decode_placement(placement)
            if horizontal:
                self.place_horizontal(x, y, word)
            else:
                self.place_vertical(x, y, word)

    def crop(self):
        width = 0
        height = 0
        for placement in self.placements:
            horizontal, x, y, word = self.decode_placement(placement)
            width = max(width, x + 1, (x + len(word)) if horizontal else x + 1)
            height = max(height, y + 1, (y + len(word)) if not horizontal else y + 1)
        self.width = width
        self.height = height
        self.init_board()

    def load_placements(self, placements: str):
        for placement in placements.split(','):
            placement = placement.strip()
            if placement[0] == '(' and placement[-1] == ')':
                self.width = GRID.find(placement[1]) + 1
                self.height = (GRID.find(placement[2]) + 1) if (len(placement) == 4) else  self.width
                self.init_board()
                continue

            if placement == '#':
                self.crop()
                continue

            if not match(PLACEMENT_PATTERN, placement):
                continue
            horizontal, x, y, word = self.decode_placement_string(placement)
            word = word.upper()
            if horizontal:
                self.place_horizontal(x, y, word)
            else:
                self.place_vertical(x, y, word)

    def render(self, empty_space: str = ' ', grid: bool = False) -> str:
        out: str = ''
        if grid:
            out += f'  {GRID[:self.width]}\n'
        i = 0
        for row in self.board:
            out += f'\n{GRID[i]} '
            i += 1
            out += ''.join(row) if empty_space == ' ' else ''.join(row).replace(' ', empty_space)
        return out

    def render_placements(self, separator: str = ', ') -> str:
        out = []
        if self.width != 15 or self.height != 15:
            if self.width == self.height:
                out.append(f'({GRID[self.width - 1]})')
            else:
                out.append(f'({GRID[self.width - 1]}{GRID[self.height - 1]})')
        for placement in self.placements:
            out.append(f"{placement[1]}{placement[2]}{'-' if placement[0] else '|'}{placement[3]}")
        return separator.join(out)

    def load_word_list(self, filename: Union[str, Path, None] = None):
        if filename is None:
            from wordlist import wordlist
            self.word_list = wordlist
            return
        filename = Path(filename).absolute()
        with open(filename, 'r') as file:
            self.word_list = file.read().strip().split('\n')
            return
        raise Exception('No word list loaded!')

    def save_word_list(self, target: Union[str, Path]) -> Optional[Path]:
        target = Path(target).absolute()
        with open(target, 'w') as f:
            for word in self.word_list:
                f.write(f'{word}\n')
            f.close()
            return target

    def secret_string(self) -> str:
        return ''.join([''.join(row) for row in self.board])

    def zlib_length(self) -> int:
        return len(compress(''.join([''.join(row) for row in self.board]).encode()))

    def sha256(self) -> sha256:
        return sha256(''.join([''.join(row) for row in self.board]).encode())

    def bytes(self) -> bytes:
        if self.encrypted_bytes:
            return self.encrypted_bytes
        self.encrypted_bytes = pwhash.argon2i.kdf(32, ''.join([''.join(row) for row in self.board]).encode() + (self.password.encode() if self.password else b''), SALT, 3, pwhash.argon2i.MEMLIMIT_SENSITIVE)  # TODO: raise from 3 to 500, only to test, also TODO: write SALT part with place, date, animal name
        return self.encrypted_bytes

    def hash(self) -> str:
        return self.sha256().hexdigest()

    def seed_words(self) -> str:
        return encode_bytes(self.bytes())

    def formated_seed_words(self, words_per_row: int = 6) -> str:
        words = self.seed_words().split(' ')
        out = ''
        i = 0
        for word in words:
            i += 1
            out += f'{i:02d}. {word:10}'
            if i % words_per_row == 0 and i != 24:
                out += '\n'
        return out

    def encrypted(self) -> bool:
        return self.password is not None

    @lru_cache
    def word_length_distribution(self) -> Dict[int, int]:
        out = {}
        for word in self.word_list:
            word_length = len(word)
            if word_length not in out:
                out[word_length] = 0
            out[word_length] +=1
        sorted_out = {}
        for length in sorted(set(out.keys())):
            sorted_out[length] = out[length]
        return sorted_out

    @lru_cache
    def letter_distribution(self) -> Dict[int, int]:
        out = {}
        for word in self.word_list:
            for char in word:
                if char not in out:
                    out[char] = 0
                out[char] +=1
        sorted_out = {}
        for letter in sorted(set(out.keys())):
            sorted_out[letter] = out[letter]
        return sorted_out

    @lru_cache
    def possibilities_first_draw_per_word_length(self) -> Dict[int, int]:
        out = {}
        for word_length, qty in self.word_length_distribution().items():
            out[word_length] = ((self.width - word_length + 1) * self.height) + ((self.height - word_length + 1) * self.width)
        return out

    @lru_cache
    def possibilities_first_draw_per_word_length_sum(self) -> Dict[int, int]:
        out = {}
        possibilities: Dict[int, int] = self.possibilities_first_draw_per_word_length()
        for word_length, length_possibilities in self.word_length_distribution().items():
            out[word_length] = length_possibilities * possibilities[word_length]
        return out

    @lru_cache
    def possibilities_sum(self) -> int:
        out = 0
        for word_length, amount in self.possibilities_first_draw_per_word_length_sum().items():
            out += amount
        return out

    @lru_cache
    def possibilities_entropy(self) -> float:
        return log2(self.possibilities_sum())

    @lru_cache
    def min_entropy(self) -> float:
        return log2((len(self.word_list)-1)**len(self.placements)) + self.possibilities_entropy()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Place words on a board.")
    parser.add_argument('--wordlist', type=str, default=None, help='The filename of the word list to load instead of the internal wordlist.')
    parser.add_argument('--size', type=int, default=None, help='The size of a square board.')
    parser.add_argument('--width', type=int, default=None, help='The width of the board.')
    parser.add_argument('--height', type=int, default=None, help='The width of the board.')
    parser.add_argument('--crop', action='store_true', help='Enable cropping.')
    parser.add_argument('--empty_char', type=str, default='·', help='The character to use for empty spaces.')
    parser.add_argument('--output', type=str, default=None, help='Store the secret key to that file')
    parser.add_argument('--password', type=str, default=None, help='Encrypt the placements with password')

    subparsers = parser.add_subparsers(dest='command')

    generate_parser = subparsers.add_parser('generate', help='Generate a board')
    generate_parser.add_argument('--min_words', type=int, default=None, help='The minimum number of words to place on the board.')
    generate_parser.add_argument('--min_letters', type=int, default=None, help='The minimum number of letters to be placed on the board.')

    load_parser = subparsers.add_parser('load', help='Load a board')
    load_parser.add_argument('placements', type=str, help='Your comma separated placements')

    args = parser.parse_args()

    width = args.width or args.size or 15
    height = args.height or args.size or 15
    board = Board(width, height, args.wordlist)
    if args.command == 'load':
        board.load_placements(args.placements)
    if args.command == 'generate':
        min_words = args.min_words or randrange(1, 5)
        min_letters = args.min_letters or randrange(10, 40)
        board.generate(min_words, min_letters)
    if args.crop:
        board.crop()
    if args.password:
        board.set_password(args.password)
    print(board.render(args.empty_char, True))
    print('')
    print(f'placements: {board.render_placements()}')
    print(f'secret string: <{board.secret_string()}>')
    if board.encrypted():
        print('')
        print(f'encrypted: yes')
        print(f'password: <{board.password}>')
    print('')
    print(f'hash: {board.hash()}')
    print('')
    print(f'seed words:\n{board.formated_seed_words(8)}')
    print('')
    print(f'minimum entropy: {board.min_entropy()}')
    print(f'zlib bytes: {board.zlib_length()}')
