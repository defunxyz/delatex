# coding=utf-8
# Copyright © The Delatex Authors. All rights reserved.

# Generic/Built-in Imports
import re, random, uuid, pathlib
from itertools import chain

# Local Custom Imports
from TexSoup import *
from lib.helpers import DebugLog, CrlfFlag, Markup, base36_encode, \
    load_json, load_yml, normalize, normalize_linebreaks, REGEX_EMAIL_ADDRESS

# Classes
class LaTeX(object):
    """
    Class for handling, manipulating, and returning plain text of LaTeX content.
    """

    # Constants
    CWD = pathlib.Path(__file__).parent
    JSON = CWD / 'json'

    # Attributes
    __slots__ = ('tex', 'accents', 'unicodes', 'text', 'random', 'flags', 'filters')

    def __init__(self, raw: str = "", flags: int = 0x0):
        super().__init__()
        self.accents = self._load_utf8_translations()
        self.unicodes = self._load_generic_utf8_symbols()
        self.text = ""
        self.tex = None
        self.random = random.Random()
        self.filters = load_yml(str(self.CWD / 'filters2.yaml'))

        if isinstance(flags, DebugLog):
            self.flags = flags.value

        if isinstance(raw, str) and raw != "":
            raw = self.preprocess(raw)
            self.tex = TexSoup(raw)

    def preprocess(self, raw: str = "") -> str:
        """Prepares raw TeX or LaTeX markup
        """
        text = raw
        text = re.sub(re.compile(r'(?<!\\)%.*', re.MULTILINE), "", text)
        text = re.sub(re.compile(r"\@{1,}"), " ", text)
        text = re.sub(re.compile(r'(?<!\\)\\ '), " ", text)

        #text = text.replace(r"\be", r"\begin{equation}")
        #text = text.replace(r"\ee", r"\end{equation}")
        #text = text.replace(r"\ba", r"\begin{eqnarray}")
        #text = text.replace(r"\ea", r"\end{eqnarray}")
        #text = text.replace(r"\bd", r"\begin{displaymath}")
        #text = text.replace(r"\ed", r"\end{displaymath}")
        #text = text.replace(r"\bea", r"\begin{eqnarray}")
        #text = text.replace(r"\eea", r"\end{eqnarray}")
        return text

    def to_text(self, src: str = "", format: bool = True) -> str:
        """Sanitizes LaTeX content to plain text and returns a clean multiline string

        Args:
            src (str): Source of LaTeX content.

        Returns:
            string : A string of clean plain text.
        """
        if not isinstance(src, str):
            raise TypeError(f"Expected string argument, was given {type(src)}.")

        if not self.tex:
            tex = self.preprocess(src)
            self.tex = TexSoup(tex)

        # Preprocess Macros
        self.tex = self._preprocess_macros(self.tex)

        # Begin specific sanitization
        self.text = self._to_plain_text(self.tex.expr.all)

        # Replace each '@' character with unique base36 encoded strings
        self.text = self._attobase36(self.text)

        # Normalize linebreaks for Unix/Linux
        self.text = normalize_linebreaks(self.text, CrlfFlag.Linux)

        # Translate LaTeX accents to their UTF8 equivalents
        self.text = self.translate_accents(self.text)

        # Generic sanitization
        self.text = self._generic_sanitization(self.text)

        # Additional formatting and fixing
        if format:
            self.text = normalize(self.text, markup=Markup.LaTeX)

        # Finally return
        return self.text


    def translate_accents(self, text: str = "") -> str:
        """Converts LaTeX accents to their UTF8 equivalents, this method ensures translation to
        human readable string"""
        for f, t in self.accents.items():
            if f in text:
                text = text.replace(f, t)
        return text

    # Private functions
    def _load_utf8_translations(self) -> dict:
        """Internal: Returns a dict of language specific UTF-8 characters"""
        return load_json(self.JSON / "translation.json" ) # Load translation symbols

    def _load_generic_utf8_symbols(self) -> dict:
        """Internal: Returns a dict of generic UTF-8 symbols and characters"""
        return load_json(self.JSON / "latex_unicode_symbols.json") # Load unicodes

    def _attobase36(self, text) -> str:
        """Internal: Converts every found @ to a unique id string in the text"""
        for c in iter(text):
            if c == '@':
                text = text.replace(c, "$" + str(base36_encode(uuid.int_(uuid.uuid4()))))
        return text

    def _generic_sanitization(self, text) -> str:
        """Internal: Uses a generic sanitization method to attempt additional clean up"""
        SHORTHANDS = re.compile(r'(Eq|Eqs|Fig|Figure|Ref|Refs|Sec)+\.+[\~]?')

        text = text.replace('``', '')
        text = text.replace('"', '')
        text = text.replace("\'\'", '')
        text = re.sub(SHORTHANDS, ' ', text)
        text = re.sub(re.compile(r'(\\|\\\\)'), '', text)
        text = re.sub(re.compile(r'(\~)'), ' ', text)
        text = re.sub(re.compile(r'(\-{2,})'), '', text)
        text = re.sub(re.compile(r'\@+'), '', text)
        text = text.replace(' .', '.')
        text = text.replace('---', '\u2014') # em dash
        text = text.replace('--', '\u2013')  # en dash
        text = re.sub(REGEX_EMAIL_ADDRESS, '[email]', text)
        return text

    def _accent_to_utf8(self, _char : str) -> str:
        """Internal: Converts LaTeX accents to their UTF8 equivalents, this method ensures translation to
        human readable string. Note: https://tex.stackexchange.com/tags/accents/info
        """
        _accent = self.accents[_char]
        return _accent if _accent else self.accents[r"\{" + _char + r"\}"]

    def _latex_to_unicode(self, key) -> str:
        """Internal: Converts almost all latex symbols to UTF-8, this method ensures conversion to
        human readable string
        """
        return self.unicodes[key]

    def _find_all_multi_attr_ex(self, macro, macros):
        """Internal: Loops over macros and extracts multiple attributes"""
        for descendant in chain(macro.contents, *[c.descendants for c in macro.children]):
            if getattr(descendant, '__match__', None) is not None:
                for name in macros:
                    if descendant.__match__(name, {}):
                        yield descendant

    def _preprocess_macros(self, tex_tree):
        """Internal: Preprocesses the LaTeX macros, and replaces instances of LaTeX macros used in-text"""
        for node in self._find_all_multi_attr_ex(tex_tree, \
        {"newcommand", "newcommand*", "renewcommand", "renewcommand*", \
        "providecommand", "providecommand*"}):
            if not len(node.args) > 0:
                continue # This line can further be expanded to highlight LaTeX invalidity

            command = node.args[0].value[1:]
            tex_tree.remove(node) # Remove the node

            if len(node.args) == 2:
                nargs = 0
                replace_str = str(node.args[1].value)
            else:
                nargs = int(node.args[1].value)
                replace_str = str(node.args[2].value)

            for usage in tex_tree.find_all(command):
                usage_str = str(replace_str)
                if len(usage.args) != nargs:
                    continue

                new_str = usage_str
                for k in range(0, nargs):
                    new_str = new_str.replace(f'#{k+1}', '{' + usage.args[k].value + '}')
                new_usage = TexSoup(new_str)
                usage.replace_with(new_usage)
        return tex_tree

    def _to_plain_text(self, tex_tree) -> str:
        """Internal: Sanitizes the LaTeX content down to clean plain text """
        text = str()
        for tex_code in tex_tree:
            if isinstance(tex_code, (TexEnv, TexCmd)):
                name = tex_code.name.lower()
                if name.endswith('*'):
                    name = name[:-1]
            if isinstance(tex_code, TexEnv):
                if name in self.filters['latex_env_to_extract']:
                    if len(tex_code.args) >= 1:
                        tex_code.args[:] = [] # Clear all of the args
                        pass

                    text += self._to_plain_text(tex_code.all)

                elif name in self.filters['latex_env_to_extract_lists']:
                    if getattr(tex_code, 'children', None) is not None:
                        text += self._to_plain_text(tex_code.children)

                elif name in self.filters['latex_env_to_discard_nbr']:
                    text += "@" if (name == "$") else "\n\n"

                else:
                    if self.flags == DebugLog.ERROR:
                        text += f"\n#Error! Unknown LaTeX environment: {tex_code.name}.\n"
                        continue
            elif isinstance(tex_code, TexCmd):
                if name in self.filters['latex_commands_to_extract']:
                    if len(tex_code.args) == 0:
                        text += self._to_plain_text(tex_code.contents)
                        continue

                    if len(tex_code.args) > 1:
                        arg = tex_code.args[0]
                        tex_code.args.remove(arg)
                        pass

                    text += self._to_plain_text(tex_code.args)

                elif name in self.filters['latex_references_to_extract']:
                    self.random.seed(tex_code.args[0].value)
                    uid = base36_encode(int(uuid.UUID(int=random.getrandbits(128), version=4)))
                    text += f"{name}—{uid}"

                elif name in self.filters['latex_commands_to_discard_inline']:
                    text += "\u0020"

                elif name in (self.filters['latex_commands_to_discard_nbr'] or \
                    self.filters['ieee_commands_to_discard_nbr'] or \
                    self.filters['latex_line_page_breakers']):
                    text += "\n"

                elif str(tex_code) in list(self.accents.keys()) or \
                    any(str(tex_code).startswith(accent) for accent in list(self.accents.keys())):
                    text += str(tex_code)

                elif str(tex_code) in self.unicodes:
                    text += self._latex_to_unicode(str(tex_code))
                else:
                    if self.flags == DebugLog.ERROR:
                        text += f"\n#Error! Unknown LaTeX command: {tex_code.name}.\n"
            elif isinstance(tex_code, (Arg, OArg, RArg)):
                text += self._to_plain_text(TexSoup(tex_code.value).expr.all)
            elif isinstance(tex_code, TokenWithPosition):
                text += tex_code.text
            elif isinstance(tex_code, TexNode):
                text += f"\n#Error! Abstraction of Tex Source, {tex_code}.\n"
            elif isinstance(tex_code, str):
                text += tex_code
            else:
                raise TypeError(f"Don't know how to handle type {type(tex_code)}")

        return text

