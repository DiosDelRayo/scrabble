from zlib import compress
from base64 import b85encode

template = """
from zlib import decompress
from base64 import b85decode
from typing import List

compressed_word_list = "{}"

wordlist: List[str] = decompress(b85decode(compressed_word_list.strip().encode())).decode().split(' ')
""".strip()

with open('all.txt', 'r') as f:
    data = f.read()
    f.close()

data = b85encode(compress(' '.join(data.strip().split('\n')).encode())).decode()


with open('wordlist.py', 'w') as f:
    f.write(template.replace('{}', data))
    f.close()
