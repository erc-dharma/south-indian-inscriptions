import os, re, collections, datetime, csv, json, unicodedata
from dharma import tree

tpl = tree.parse("tpl.xml")
today = datetime.datetime.today().strftime("%Y-%m-%d")
tpl.first("//change[@who='part:mime']")["when"] = today
this_dir = os.path.dirname(__file__)
out_dir = os.path.join(os.path.dirname(this_dir), "3out")
biblio_refs = {}
biblio_editors = {}

scripts = {
	"arab": ("arabic", None),
	"brtr": ("brāhmī", "late"), # Only one inscription
	"de": ("nāgarī", None),
	"detr": ("nāgarī", None),
	"dutch": ("latin", None),
	"eng": ("latin", None),
	"gr": ("grantha", "vernacular"),
	"greek": ("greek", None),
	"ka": ("kannada", None),
	"katr": ("kannada", None),
	"lat": ("latin", None),
	"malayalam": ("malayalam", None),
	"pers": ("persian", None),
	"pr": ("brāhmī", None),
	"prtr": ("brāhmī", None),
	"simtr": ("siṃhala", None),
	"skttr": ("brāhmī", None), # Only one inscription
	"ta": ("tamil", "vernacular"),
	"te": ("telugu", "vernacular"),
	"tetr": ("telugu", "vernacular"),
	"urdu": ("urdu", None),
}

languages = {
	"arab": "ara",
	"brtr": None,
	"de": None,
	"detr": None,
	"dutch": "nld",
	"eng": "eng",
	"gr": None,
	"greek": "grk",
	"ka": "kan",
	"katr": "kan",
	"lat": "lat",
	"malayalam": "mal",
	"pers": "per",
	"pr": "pra",
	"prtr": "pra",
	"simtr": "sin",
	"skttr": "san",
	"ta": "tam",
	"te": "tel",
	"tetr": "tel",
	"urdu": "urd",
}

scripts_ignore = {}
for tag, infos in scripts.items():
	scripts_ignore.setdefault(infos, set()).add(tag)

def strings_in(root):
	for node in root:
		match node:
			case tree.String():
				yield node
			case tree.Tag():
				yield from strings_in(node)
			case _:
				pass

def language_and_script_of(ins):
	ins = ins.copy()
	for ce in ins.find("//ce"):
		ce.delete()
	for note in ins.find("//note"):
		note.delete()
	langs_freqs = collections.defaultdict(int)
	langs_freqs[None] = -1
	scripts_freqs = collections.defaultdict(int)
	scripts_freqs[None] = -1
	for l in ins.find("//l"):
		for node in strings_in(l):
			length = sum(not c.isspace() for c in node.data)
			lang = script = None
			while not lang or not script:
				node = node.parent
				if node is l:
					break
				if not lang:
					lang = languages.get(node.name)
				if not script:
					script = scripts.get(node.name)
			langs_freqs[lang] += length
			scripts_freqs[script] += length
	lang = max(langs_freqs, key=lambda k: langs_freqs[k])
	if ins["lang"]:
		lang = ins["lang"]
		assert len(lang) == 3
	script = max(scripts_freqs, key=lambda k: scripts_freqs[k]) or (None, None)
	return lang, script

def pad_ins_num(x):
	i = 0
	while i < len(x) and x[i].isdigit():
		i += 1
	num, letters = int(x[:i]), x[i:]
	return f"{num:04}{letters}"

def inscription_id(vol_no, section_no, ins_no):
	if "-" in ins_no:
		s, e = ins_no.split("-")
		padded_ins_no = f"{pad_ins_num(s)}-{pad_ins_num(e)}"
	else:
		padded_ins_no = f"{pad_ins_num(ins_no)}"
	return f"DHARMA_INSSIIv{vol_no:02}p{section_no}i{padded_ins_no}"

# biblio.tsv holds mappings SII volume -> short title. Relevant biblio entries
# are under E-SII in our bibliography.
def load_biblio():
	global biblio_refs, biblio_editors
	with open("biblio.csv") as f:
		for fields in csv.reader(f):
			volume = fields[0]
			assert volume not in biblio_refs
			if not fields[2]:
				biblio_refs[volume] = None
				biblio_editors[volume] = None
			else:
				biblio_refs[volume] = fields[1]
				editors = json.loads(fields[2])
				out = ""
				for i, ed in enumerate(editors):
					assert ed["firstName"] and ed["lastName"]
					if i > 0 and i == len(editors) - 1:
						out += " and "
					elif i > 0:
						out += ", "
					out += ed["firstName"] + " " + ed["lastName"]
				biblio_editors[volume] = out

def following(node):
	def inner(nodes):
		for node in nodes:
			yield node
			if isinstance(node, tree.Tag):
				yield from inner(node)
	while not isinstance(node, tree.Tree):
		i = node.parent.index(node)
		yield from inner(node.parent[i + 1:])
		node = node.parent

def only_blank_after(node):
	for stuff in following(node):
		match stuff:
			case tree.String() if not stuff.data.strip():
				pass
			case tree.Comment():
				pass
			case _:
				return False
	return True

def inscription_page_range(ins):
	pages = set()
	for node in ins.find("//*[@n]"):
		# Deal with the last pb in the ins. Only take it into account if
		# what follows in the file is nothing but blank strings.
		assert isinstance(ins.parent, tree.Tree)
		if node.name == "pb" and only_blank_after(node):
			continue
		page = int(node["n"].split(":")[1].split("-")[0])
		pages.add(page)
	pages = sorted(pages)
	assert len(pages) > 0
	if len(pages) == 1:
		return f"{pages[0]}"
	assert pages == list(range(pages[0], pages[-1] + 1)), pages
	return f"{pages[0]}-{pages[-1]}"

def iter_strings(node, ignore_notes=False):
	match node:
		case tree.String():
			yield node
		case tree.Tag() if ignore_notes and node.name == "note":
			pass
		case tree.Tag() if node.name == "ce":
			pass
		case tree.Tag() | tree.Tree():
			for kid in node:
				yield from iter_strings(kid, ignore_notes=True)

def strings(node):
	return list(iter_strings(node))

def merge_adjacent_gr(ins):
	t = ins.tree
	for node in ins.find("//hi[@rend='grantha']"):
		if node.tree is not t:
			continue
		i = j = node.parent.index(node)
		after = node
		while (after := after.first("stuck-following-sibling::hi[@rend='grantha']")):
			j = after.parent.index(after)
		for after in node.parent[i + 1:j + 1]:
			node.append(after)
			if isinstance(after, tree.Tag) and after.matches("hi[@rend='grantha']"):
				after.unwrap()
	ins.coalesce()

def delete_lb_break_no(node):
	def starts_with_upper(r):
		r = r.data.lstrip()
		if len(r) == 0:
			return False
		return r[0].isupper()
	# dans les originaux -<lb break="no"/> virer et le tag et le - SAUF si majuscule après
	before = preceding_string(node)
	after = following_string(node)
	if before.data.rstrip().endswith("-"):
		if not starts_with_upper(after):
			before.replace_with(before.data.rstrip()[:-1])
			after.replace_with(after.data.lstrip())
		node.delete()
	else:
		node.replace_with(" ")

def following(node):
	def inner(nodes):
		for node in nodes:
			yield node
			if isinstance(node, tree.Tag):
				yield from inner(node)
	while not isinstance(node, tree.Tree):
		parent = node.parent
		i = parent.index(node)
		yield from inner(parent[i + 1:])
		node = parent

def preceding(node):
	def inner(nodes):
		for node in reversed(nodes):
			yield node
			if isinstance(node, tree.Tag):
				yield from inner(node)
	while not isinstance(node, tree.Tree):
		parent = node.parent
		i = node.parent.index(node)
		yield from inner(parent[:i])
		node = parent

def preceding_string(node):
	for node in preceding(node):
		if isinstance(node, tree.String):
			return node

def following_string(node):
	for node in following(node):
		if isinstance(node, tree.String):
			return node

def replace_between_vowels(r):
	# VṭV, VṇV, VtV, VttV, VnV, VyV, VvV, VntV
	# <gr>XVṭVX</gr> -> <gr>X</gr>VṭV<gr>X</gr>
	tmp = tree.Tag("tmp")
	i = 0
	s = r[0]
	for m in re.finditer(r"(?:[aāiīuūeēoō]+|^)((?:ṭ|ṇ|t|tt|n|y|v|nt)[aāiīuūeēoō]+)", s.data):
		d = s.data[i:m.start(1)]
		if d:
			gr = tree.Tag("gr")
			gr.append(d)
			tmp.append(gr)
		g1 = m.group(1)
		if g1.startswith("nt"):
			g1 = "n=t" + g1[2:]
		tmp.append(g1)
		i = m.end()
	d = s.data[i:]
	if d:
		gr = tree.Tag("gr")
		gr.append(d)
		tmp.append(gr)
	r.replace_with(tmp)
	tmp.unwrap()

def cleanup_inscription(ins, lang):
	ins.coalesce()
	for node in ins.find("//lb"):
		assert node.empty
		delete_lb_break_no(node)
	for pb in ins.find("//pb"):
		assert pb.empty
		pb.delete()
	if lang == "tam":
		for i in range(3):
			ins.coalesce()
			for gr in ins.find("//gr[plain() and not empty()]"):
				if len(gr) > 1:
					continue
				assert isinstance(gr[0], tree.String)
				replace_between_vowels(gr)
	ins.coalesce()
	for gr in ins.find("//gr"):
		gr.name = "hi"
		gr["rend"] = "grantha"
	for i in ins.find("//i"):
		i.name = "hi"
		i["rend"] = "italic"
	for b in ins.find("//b") + ins.find("//em"):
		b.name = "hi"
		b["rend"] = "bold"
	for ch in ins.find("//ch"):
		ch.replace_with("�")
	for node in ins.find("//list"):
		node.unwrap()
	for note in ins.find("//note"):
		_, p, n = re.fullmatch(r"([1-9][0-9]*):([1-9][0-9]*)-(.+)", note["n"]).groups()
		note["n"] = f"{p}-{n}"

def add_gaps(s):
	ret = tree.Tag("root")
	i = 0
	for m in re.finditer(r"[.•](\s*[.•])*", s):
		start, end = m.start(), m.end()
		n = sum(not c.isspace() for c in m.group())
		ret.append(s[i:start])
		ret.append(" ")
		ret.append(tree.Tag("gap", reason="lost", quantity=str(n), unit="character"))
		ret.append(" ")
		i = end
	ret.append(s[i:])
	ret.coalesce()
	return ret

def process_brackets(s):
	ret = tree.Tag("root")
	i = 0
	for m in re.finditer(r"\[((?:[\w\s]+\*?)|(?:\|?\|\*))\]", s):
		start, end = m.start(), m.end()
		what = m.group(1)
		ret.append(s[i:start])
		if what == "||*":
			# <supplied reason="undefined"><g type="ddanda">.</g></supplied>
			supplied = tree.Tag("supplied", reason="undefined")
			g = tree.Tag("g", type="ddanda")
			g = tree.Tag("g", ref="sym:doubleBar", type="punctuation")
			g.append(".")
			supplied.append(g)
			ret.append(supplied)
		elif what == "|*":
			# <supplied reason="undefined"><g type="danda">.</g></supplied>
			supplied = tree.Tag("supplied", reason="undefined")
			g = tree.Tag("g", type="danda")
			g = tree.Tag("g", ref="sym:bar", type="punctuation")
			g.append(".")
			supplied.append(g)
			ret.append(supplied)
		elif what in ("ā*", "ī*", "ū*"):
			long = what.rstrip("*")
			breve = unicodedata.normalize("NFD", long)[0]
			choice = tree.Tag("choice")
			sic = tree.Tag("sic")
			sic.append(breve)
			corr = tree.Tag("corr")
			corr.append(long)
			choice.append(sic)
			choice.append(corr)
			ret.append(choice)
		elif what.endswith("*"):
			what = what.rstrip("*")
			supplied = tree.Tag("supplied", reason="omitted")
			supplied.append(what)
			ret.append(supplied)
		else:
			unclear = tree.Tag("unclear")
			unclear.append(what)
			ret.append(unclear)
		i = end
	ret.append(s[i:])
	return ret

def remove_useless_headers(node):
	for head in node.find("h4[@ignore='yes']"):
		for elem in head:
			if isinstance(elem, tree.String):
				elem.delete()
		head.unwrap()

def replace_ddanda_dash(s):
	ret = tree.Tag("root")
	i = 0
	for m in re.finditer("\\|\\|([-\N{em dash}])", s):
		start, end = m.start(1), m.end(1)
		ret.append(s[i:start])
		# <g type="dashLong">.</g>
		if m.group(1) == "-":
			tag = tree.Tag("g", type="dash")
			tag = tree.Tag("g", ref="sym:dash", type="punctuation")
		else:
			tag = tree.Tag("g", type="dashLong")
			tag = tree.Tag("g", ref="sym:dash-long", type="punctuation")
		tag.append(".")
		ret.append(tag)
		i = end
	ret.append(s[i:])
	return ret

def trim_before(node):
	parent = node.parent
	i = parent.index(node)
	if i > 0 and isinstance(parent[i - 1], tree.String) and parent[i - 1].endswith(" "):
		parent[i - 1].replace_with(parent[i - 1].data.rstrip())

def add_edition_stuff(edition):
	for l in edition.find(".//l"):
		for func in (add_gaps, process_brackets, replace_ddanda_dash):
			l.coalesce()
			for s in strings(l):
				ret = func(s.data)
				s.replace_with(ret)
				ret.unwrap()

def is_vowel(c):
	return unicodedata.normalize("NFD", c.lower())[0] in "aeiou"

def fix_initials(node, initial):
	for sn in strings(node):
		i = 0
		s = sn.data
		while i < len(s):
			if initial and is_vowel(s[i]):
				s = s[:i] + s[i].upper() + s[i + 1:]
				initial = False
			elif initial and i + 1 < len(s) and s[i] == "\N{middle dot}" and is_vowel(s[i + 1]):
				s = s[:i] + s[i + 1].upper() + s[i + 2:]
				initial = False
			elif s[i] == " ":
				initial = True
			else:
				initial = False
			i += 1
		if sn.data != s:
			sn.replace_with(s)

def fix_lines(edition):
	brk = True
	para = None
	prev_l_following = None
	for l in edition.find("l"):
		if prev_l_following is not l:
			para = tree.Tag("p")
			para.append("\n")
			l.insert_before(para)
		prev_l_following = l.stuck_following_sibling()
		para.append(l)
		_, _, _, n = re.fullmatch(r"([1-9][0-9]*):([1-9][0-9]*):([^:]+):(.+)", l["n"]).groups()
		fix_initials(l, brk)
		if not brk:
			l.prepend(tree.Tag("lb", n=n, break_="no"))
		else:
			l.prepend(tree.Tag("lb", n=n))
		ss = strings(l)
		brk = True
		while ss:
			s = ss.pop()
			if s.isspace():
				continue
			if s.data.rstrip().endswith("-"):
				repl = s.data.rstrip()
				if repl != s.data:
					repl = repl[:-1] + " "
				else:
					repl = repl[:-1]
				s.replace_with(repl)
				brk = False
			break
		l.append("\n")
		l.unwrap()

def fix_langs(ins, lang, script_info):
	for tag in scripts_ignore.get(script_info, set()):
		for node in ins.find(f".//{tag}"):
			node.unwrap()
	for node in ins.find(".//*"):
		if not node.name in languages and not node.name in scripts:
			continue
		node.attrs.clear()
		lang = languages.get(node.name)
		if lang:
			node["lang"] = f"{lang}-Latn"
		klass, maturity = scripts.get(node.name, (None, None))
		if klass:
			node["rendition"] = f"class:{klass} maturity:{maturity or 'undetermined'}"
		node.name = "seg"

def make_readable_ins_id(vol_no, section_no, ins_no):
	if not section_no:
		return f"{vol_no}.{ins_no}"
	if vol_no != 32 and section_no == 1:
		return f"{vol_no}.{ins_no}"
	if vol_no == 32 and section_no == 3 or vol_no != 32 and section_no > 1:
		return f"{vol_no}, appendix, no. {ins_no}"
	return f"{vol_no}, part {section_no}, no. {ins_no}"

def encode_num(num):
	ret = tree.Tag("num", value=str(num))
	i = 1
	parts = []
	while num:
		rem = num % (i * 10)
		num -= rem
		parts.append((rem // i, i))
		i *= 10
	parts.reverse()
	sep = ""
	for digit, multiplier in parts:
		if digit == 0:
			continue
		if digit > 1 or multiplier == 1:
			ret.append(sep)
			ret.append(str(digit))
			sep = " "
		if multiplier > 1:
			ret.append(sep)
			g = tree.Tag("g", type="numeral")
			g.append(str(multiplier))
			ret.append(g)
			sep = " "
	return ret

def encode_grantha_nums(ins):
	ins.coalesce()
	for gr in ins.find(".//gr"):
		ss = strings(gr)
		for sn in ss:
			tmp = tree.Tag("tmp")
			i = 0
			for m in re.finditer("[1-9][0-9]+", sn.data):
				tmp.append(sn.data[i:m.start()])
				tmp.append(encode_num(int(m.group())))
				i = m.end()
			tmp.append(sn.data[i:])
			sn.replace_with(tmp)
			tmp.unwrap()
	ins.coalesce()
	for gr in ins.find(".//gr[stuck-child::num]"):
		if len(gr) == 1:
			gr.unwrap()
	ins.coalesce()
	for gr in ins.find(".//gr[plain() and regex('^[1-9]$')]"):
		assert len(gr) == 1
		if gr[0].isdigit():
			gr.unwrap()

def replace_grantha_syllables(ins):
	for ta in ins.find(".//ta"):
		for sn in strings(ta):
			tmp = tree.Tag("tmp")
			i = 0
			for m in re.finditer("((?:j|s|ṣ|kṣ|h)[aāiīuūeēoō]+)|śrī", sn.data, re.I):
				tmp.append(sn.data[i:m.start()])
				gr = tree.Tag("gr")
				gr.append(m.group())
				tmp.append(gr)
				i = m.end()
			tmp.append(sn.data[i:])
			sn.replace_with(tmp)
			tmp.unwrap()

def replace_dandas(sn):
	repl = tree.Tag("root")
	i = 0
	for m in re.finditer(r"\|+", sn.data):
		repl.append(sn.data[i:m.start()])
		n = len(m.group())
		if n == 2:
			g = tree.Tag("g", type="ddanda")
			g = tree.Tag("g", ref="sym:doubleBar", type="punctuation")
			g.append(".")
			repl.append(g)
		else:
			while n > 0:
				g = tree.Tag("g", type="danda")
				g = tree.Tag("g", ref="sym:bar", type="punctuation")
				g.append(".")
				repl.append(g)
				n -= 1
		i = m.end()
	repl.append(sn.data[i:])
	sn.replace_with(repl)
	repl.unwrap()

def process_inscription(ins, vol_no, part_no, section_no, ins_no):
	ins = ins.copy()
	lang, script_info = language_and_script_of(ins)
	# <gr> ou <de>, ṛi > ṛ
	for node in ins.find("//gr") + ins.find("//de"):
		for sn in strings(node):
			sn.replace_with(sn.data.replace("ṛi", "ṛ"))
	if lang == "tam":
		for gr in ins.find("//gr"):
			for sn in strings(gr):
				s = sn.data
				s = s.replace("ē", "e").replace("ō", "o")
				s = s.replace("Ē", "E").replace("Ō", "O")
				if sn.data != s:
					sn.replace_with(s)
		ins.coalesce()
		replace_grantha_syllables(ins)
		ins.coalesce()
		encode_grantha_nums(ins)
		ins.coalesce()
	if lang == "tel" or lang == "kan":
		for sn in strings(ins):
			s = sn.data
			s = s.replace("¨r", "r")
			s = s.replace("n®", "N")
			if sn.data != s:
				sn.replace_with(s)
	for ta in ins.find("//ta"):
		for sn in strings(ta):
			s = sn.data.replace("g", "ṅ")
			# '- Āvatu' >> <g type="dash"/>Āvatu
			tmp = tree.Tag("tmp")
			i = 0
			for m in re.finditer(r'-\s*Āvatu', s, re.I):
				tmp.append(s[i:m.start()])
				tmp.append(tree.Tag("g", ref="sym:dash", type="punctuation"))
				tmp.append("Āvatu")
				i = m.end()
			tmp.append(s[i:])
			sn.replace_with(tmp)
			tmp.unwrap()
	ins.coalesce()
	script_class, script_maturity = script_info
	ins_page_range = inscription_page_range(ins)
	cleanup_inscription(ins, lang)
	ins.coalesce()
	out = tpl.copy()
	def assign_volume_to(ident, firstname, lastname):
		persName = out.first("//titleStmt//persName")
		persName.clear()
		persName["ref"] = f"part:{ident}"
		forename = tree.Tag("forename")
		forename.append(firstname)
		surname = tree.Tag("surname")
		surname.append(lastname)
		persName.append("\n" + 6 * "\t")
		persName.append(forename)
		persName.append("\n" + 6 * "\t")
		persName.append(surname)
		persName.append("\n" + 5 * "\t")

		tmp = tree.parse_string(f'<change who="part:{ident}" when="0000-00-00" status="draft">Further conversion of digital encoding to DHARMA encoding scheme according to EGD (Encoding Guide for Diplomatic Editions)</change>')
		out.first("//revisionDesc").prepend(tmp.root)
		out.first("//revisionDesc").prepend("\n" + 3 * "\t")

		for sn in strings(out):
			s = sn.data.replace("automatically converted to DHARMA conventions", f"converted to DHARMA conventions by {firstname} {lastname}")
			if s != sn.data:
				sn.replace_with(s)
	if vol_no in (1, 2, 3, 4, 12, 13, 14, 17, 19):
		assign_volume_to("emfr", "Emmanuel", "Francis")
	elif vol_no in (7, 6, 8) and lang == "tam":
		assign_volume_to("doop", "Dorotea", "Operato")
	elif vol_no in (5,) and lang == "tam":
		assign_volume_to("reda", "Renato", "Dávalos")
	title = out.first("//titleStmt/title[@type='alt']")
	head = ins.first("head")
	for elem in head.find(".//*"):
		elem.unwrap()
	title.append(head)
	head.unwrap()
	summ = out.first("//summary")
	for elem in list(ins):
		if isinstance(elem, tree.Tag) and elem.name in ("edition", "translation"):
			break
		if isinstance(elem, tree.Tag) and re.fullmatch("h[0-9]+", elem.name):
			elem.name = "p"
		summ.append(elem)
		summ.append("\t" * 6)
	ins_id = inscription_id(vol_no, section_no, ins_no)
	out.first("//idno").append(ins_id)
	readable_ins_id = make_readable_ins_id(vol_no, section_no, ins_no)
	volume_editor = biblio_editors[part_no and f"{vol_no}-{part_no}" or f"{vol_no}"]
	for s in strings(out.first("//TEI")):
		tmp = s.data
		tmp = tmp.replace("{ins_readable_id}", readable_ins_id)
		if volume_editor:
			tmp = tmp.replace("{volume_editor}", volume_editor)
		if tmp != s.data:
			s.replace_with(tmp)
	short_title = biblio_refs[part_no and f"{vol_no}-{part_no}" or f"{vol_no}"]
	if short_title:
		for ptr in out.find("//bibl/ptr"):
			ptr["target"] = f"bib:{short_title}"
	out.first("//citedRange[@unit='page']").append(ins_page_range)
	out.first("//citedRange[@unit='item']").append(ins_no)
	ed_parts = ins.find("edition")
	out_ed = out.first("//div[@type='edition']")
	out_ed["lang"] = f"{lang}-Latn" if lang else "und"
	out_ed["rendition"] = f"class:{script_class or 'undetermined'} maturity:{script_maturity or 'undetermined'}"
	if ed_parts:
		for elem in ed_parts:
			fix_langs(elem, lang, script_info)
			add_edition_stuff(elem)
			fix_lines(elem)
			remove_useless_headers(elem)
			for head in elem.find("h4"):
				head.comment_out()
			elem.coalesce()
			merge_adjacent_gr(elem)
			elem.coalesce()
			for sn in strings(elem):
				replace_dandas(sn)
			out_ed.append(elem)
			elem.unwrap()
	trans_parts = ins.find("translation")
	out_trans = out.first("//div[@type='translation']")
	if trans_parts:
		out_trans["source"] = f"bib:{short_title}"
		for elem in trans_parts:
			remove_useless_headers(elem)
			out_trans.append(elem)
			elem.unwrap()
	else:
		out_trans.delete()
	if vol_no == 14 and lang in ("tam", "und"):
		out.first("//div[@type='edition']").prepend(tree.Comment("Check script: Vaṭṭeḻuttu?"))
	out = out.xml()
	out = out.replace("[||*]", '<supplied reason="undefined"><g ref="sym:doubleBar" type="punctuation">.</g></supplied>')
	out = out.replace("[|*]", '<supplied reason="undefined"><g ref="sym:bar" type="punctuation">.</g></supplied>')
	out = re.sub(r"</note> \w", lambda m: m.group().replace(" ", ""), out)
	out = re.sub(r"·([aāiīuūeēoō]+)", lambda m: m.group(1).capitalize(), out)
	out = out.replace("- vatu", '<g ref="sym:dash" type="punctuation"/>vatu')
	out = out.replace(" <note", "<note")
	if vol_no in (1, 2, 3):
		out = out.replace("</note>", "</note> ")
	out = re.sub(r"\n{3,}", "\n\n", out, flags=re.DOTALL)
	out = re.sub(r"[ ]{2,}", " ", out)
	return out

def process_section(root, vol_no, part_no, section_no):
	for ins in root.find(".//inscription"):
		print(ins)
		ins_no = ins["n"].rsplit(":")[-1]
		ins_id = inscription_id(vol_no, section_no, ins_no)
		out = process_inscription(ins, vol_no, part_no, section_no, ins_no)
		with open(f"{out_dir}/{vol_no:02}/~{ins_id}.xml", "w") as f:
			f.write(out)

def delete_all_files(path):
	for root, dirs, files in os.walk(path):
		for file in files:
			os.remove(os.path.join(root, file))

def iter_volumes():
	volumes_dir = os.path.join(this_dir, "volumes")
	for file in sorted(os.listdir(volumes_dir)):
		if not file.endswith(".xml"):
			continue
		t = tree.parse(os.path.join(volumes_dir, file))
		yield t.first("volume")

def save_all():
	delete_all_files(out_dir)
	for vol in iter_volumes():
		print(vol)
		xs = vol["n"].split("-")
		vol_no = int(xs[0])
		if len(xs) == 1:
			part_no = 0
		else:
			part_no = int(xs[1])
			assert part_no > 0
		os.makedirs(f"{out_dir}/{vol_no:02}", exist_ok=True)
		sections = vol.find(".//part")
		if sections:
			for section_no, node in enumerate(sections, 1):
				process_section(node, vol_no, part_no, section_no)
		else:
			process_section(vol, vol_no, part_no, 0)


def make_tsv(f):
	print("volume:page:inscription", "lang", "script class", "script maturity", sep="\t", file=f)
	for vol in iter_volumes():
		for ins in vol.find("//inscription"):
			lang, (script_class, script_maturity) = language_and_script_of(ins)
			print(ins["n"], lang or "?", script_class or "?", script_maturity or "?", sep="\t", file=f)

load_biblio()

if __name__ == "__main__":
	save_all()
	with open(f"{out_dir}/meta.tsv", "w") as f:
	 	make_tsv(f)
