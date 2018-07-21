import operator, logging, json, struct, argparse, sys
from bisect import bisect_left
from time import time
from collections import defaultdict
from bitarray import bitarray


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def timethis(f):
	def wrap(*args):
		time_a = time()
		result = f(*args)
		time_b = time()
		timed = time_b - time_a
		logger.debug(' {} function took {} seconds'.format(f.func_name, timed))
		return result
	return wrap


class KeyList(object):
	def __init__(self, l, key):
		self.l = l
		self.key = key

	def __len__(self):
		return len(self.l)

	def __getitem__(self, index):
		return self.key(self.l[index])


class Huffman(object):
	def __init__(self):
		self.now = time()
		self.frequency = defaultdict(lambda:0)
		self.huffman_tree = {}
		self.huffman_codes = {}

	def calculate_frequency(self, input_file):
		try:
			self.output_file = input_file.split('.')[0] + '.bin'
		except:
			self.output_file = input_file + '.bin'

		with open(input_file, 'r') as open_file:
			self.text = open_file.read()
			self.data = bytearray(self.text)
		
		for character in self.data:
			self.frequency[character] += 1

	def calculate_huffman_tree(self):
		self.stack = sorted(self.frequency.items(), key=operator.itemgetter(1))
		self.stack = [(chr(x), y) for x, y in self.stack]
		self.chars = [x[0] for x in self.stack]

		while True:
			if len(self.stack) == 1:
				break

			a = self.stack.pop(0)
			b = self.stack.pop(0)

			node = character, freq = a[0] + b[0], a[1] + b[1]

			idx = bisect_left(KeyList(self.stack, key=lambda x: x[1]), freq)
			
			self.stack.insert(idx, node)
			self.huffman_tree[character] = a[0], b[0]

		self.root = character
		self.keys = self.huffman_tree.keys()
		self.values = self.huffman_tree.values()

		for character in self.chars:
			original = ord(character)
			bits = ''
			idx = None

			while True:
				if character == self.root:
					break

				for i, (a, b) in enumerate(self.values):
					if character == a:
						bits += '0'
						idx = i
						break

					elif character == b:
						bits += '1'
						idx = i
						break

				character = self.keys[idx]

			self.huffman_codes[original] = bits[::-1]

	def encode(self):
		self.bitstring = bitarray()
		self.bitstring.encode({chr(a):bitarray(b) for a, b in self.huffman_codes.items()}, self.text)
		self.bitstream = bitarray(self.bitstring)

	def prefix(self):
		self.prefix_dict = json.dumps(self.huffman_codes)
		self.prefix_bytes = bytes(self.prefix_dict)
		self.prefix_length = bitarray(bin(len(self.prefix_bytes))[2:])[::-1]

		for i in range(32 - len(self.prefix_length)):
			self.prefix_length.append(False)
		self.prefix_length = self.prefix_length[::-1]

		self.leftover = 8 - len(self.bitstream) % 8
		self.leftover = self.leftover if self.leftover != 8 else 0
		self.zeros = bitarray(bin(self.leftover)[2:])[::-1]

		for i in range(32 - len(self.zeros)):
			self.zeros.append(False)
		self.zeros = self.zeros[::-1]

	def tofile(self):
		with open(self.output_file, 'wb') as open_file:
			self.zeros.tofile(open_file)
			self.prefix_length.tofile(open_file)
			open_file.write(self.prefix_bytes)
			self.bitstream.tofile(open_file)

		self.ratio = (len(self.bitstream) + 8 * 8 + len(self.prefix_bytes)) / len(self.data) * 8

	def fromfile(self, file_in):
		try:
			self.output_file = file_in.split('.')[0] + '.txt'
		except:
			self.output_file = file_in + '.txt'

		self.length_string = ''
		self.zeros_string = ''

		with open(file_in, 'rb') as open_file:
			for i in range(4):
				self.zeros_string += open_file.read(1)

			self.zeros_to_remove = struct.unpack('>i', self.zeros_string)[0]

			for i in range(4):
				self.length_string += open_file.read(1)

			self.bytes_to_read = struct.unpack('>i', self.length_string)[0]
			self.raw_json = bytearray()

			for i in range(self.bytes_to_read):
				self.raw_json.append(open_file.read(1))

			self.huffman_dict = eval(str(self.raw_json))
			self.compressed_data = bitarray()
			self.compressed_data.fromfile(open_file)
			self.compressed_data = str(self.compressed_data)
			self.bits = self.compressed_data.split("'")[1]

	def decode(self):
		self.lookup = {chr(int(a)):bitarray(b) for a, b in self.huffman_dict.items()}
		if self.zeros_to_remove:
			self.bits = self.bits[:-1 * self.zeros_to_remove]

		self.decoded = ''.join(bitarray(self.bits).decode(self.lookup))

		with open(self.output_file, 'w') as open_file:
			open_file.write(self.decoded)

	@timethis
	def compress(self, file_name):
		self.calculate_frequency(file_name)
		self.calculate_huffman_tree()
		self.encode()
		self.prefix()
		self.tofile()

	@timethis
	def decompress(self, file_name):
		self.fromfile(file_name)
		self.decode()


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description = 'Compress or decompress a file using Huffman algorithm')
	parser.add_argument('-d', action = 'store_true', help = 'Use -d if you like to decompress')
	parser.add_argument('filename', type = str, nargs = 1, help = 'file name of the file you want to compress/decompress')
	
	try:
		namespace = parser.parse_args(sys.argv[1:])
	except:
		namespace = parser.parse_args(['test.txt'])
	

	if not namespace.d:
		huffman = Huffman()
		start = time()
		huffman.compress(namespace.filename[0])
		print 'File compressed by {}%, in {} seconds'.format(huffman.ratio, round(time() - start, 8))
	else:
		huffman = Huffman()
		start = time()
		huffman.decompress(namespace.filename[0])
		print 'File decompressed to original in {} seconds'.format(round(time() - start, 8))