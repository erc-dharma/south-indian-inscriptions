# Elements

arab	contents in Arabic script
arn	contents is an Arabic number in an inscription that is not in the Latin
	script. very few occurrences, should be removed eventually.
b	bold
brtr	Brāhmī script transliterated by the volume's editor
c1,c2,...
	table cells
ce	used to annotate observation of the editor like "damaged" etc. within
	an inscription's text. the contents is in English.
ch	represents a character the person who did the XML encoding cannot read.
	the element is always empty. we have two forms: <ch/> and <ch xx="ç"/>.
	can't tell whether the difference is significant, so I left things like
	that).
de	contents in Devanāgarī
detr	Devanāgarī script transliterated by the editor
dutch	text in Dutch and in the Latin script
edition	delimits the "edition" part of an inscription viz. what should go into
	div[@type='edition'] in EpiDoc
em	emphasis, only used for a few volumes. visually, have either bold or
	extra space between letters, depending on the volume (or maybe the
	reedition?)
eng	text in English
g	gaiji, like in TEI. only two forms: <g type="pillaiyarc"> and
	<g type="symbol">
gr	Grantha
greek	contents in Greek alphabet in the PDFs, transliterated in the XML.
group
	group of inscriptions (has inscriptions as children). can be nested.
head
	heading of a single inscription
h1,h2,h3,h4,h5
	headings. heading levels are not consistent, and not all headings are
	marked up as such (we find some represented as <p>).
	h1 and h2 are for volume-level titles
	h3 are for groups of inscriptions
	h4 and h5 are for titles within inscriptions, typically milestones.
i	italics
inscription
	a single inscription
ka	Kannada script
katr	Kannada script transliterated by the volume's editor
l	inscription line. line numbers are often not unique within a given
	inscription. there are also <l> elements within notes.
lat	contents in Latin language and in Latin script
lb	line breaks in the PDF
list	list of numbered paragraphs
malayalam
	Malayalam
note	footnote. some are empty.
part	element added to delimit sections of a volume when the same inscription
	number appears in several sections of this volume. this should not be
	used for structuring the output, only to generate unique ids.
p	paragraph
pb	page break in the PDF
pers	Persian alphabet
pr	Prakrit
prtr	Prakrit, transliterated by the editor
simtr	Simhala script, transliterated by the editor
skttr	Sanskrit language, transliterated by the editor.
ta	in Tamil script and Tamil language
table	tables (some have cells <c1>, etc.; some are not formatted)
te	Telugu
tetr	Telugu transliterated by the editor
tlka	probably: telugu or kannada. used as placeholder by Malthen
translation
	delimits the translation of an inscription, which should go into
	div[@type='translation'] in EpiDoc.
unkntr	transliteration of unknown script(?)
urdu	urdu
volume	book volume

# Notes

The editor uses A, B, C for preventing inscriptions numbers collisions. I have corrected various numbering issues. If the inscription number in the filename is not the same as the one in the file, this is because there was a numbering issue in the original. The "correct" inscription number is the one in the filename, not the one in the file itself. The latter should be amended with e.g. sic/corr.

Duplicate inscriptions numbers within a single volume are handled like this:
* Sometimes, the inscription is described in the body of a volume, but the
  inscription's contents is given in an annex. In this case, the letter Z is
  added to the inscription's number in the annex.
* Sometimes, inscription numbers are local to a part of the volume, to its
  parts or to an annex. In this case, we create "parts" to avoid the confusion.
  They are encoded with a <part> element in the XML.
* Otherwise (for only a single inscription), the letter Y is added to the
  inscription number.

It is likely some footnote page numbers are wrong. In a few instances, they occur on the next page. I might have introduced errors while reassigning footnote numbers.

I have probably unintentionally removed some placeholders (empty <tl/> and <tlka/> elements).

There can be several <edition> and <translation> in a single inscription. But they should alternate and cover eveything upto the end of the inscription.

To <h4> that are only useful to indicate the start of the edition or of the translation, viz. to those that only contain some form of the string "Text" or "Translation" (_and_ optionally some <note>), I added @ignore="yes". The contents of these element's <note> can be useful, but the heading itself is useless and can be dropped in the output.
