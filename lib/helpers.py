# coding=utf-8
# Copyright © The Delatex Authors. All rights reserved.

# Generic/Built-in Imports
import enum, re, json, string, yaml, pickle, datetime
import platform
from pathlib import Path
import chardet

__all__ = ["CrlfFlag", "detect_encoding", "DebugLog", "Markup", "base36_encode", "base36_decode", "load_json",
           "load_yml", "normalize", "normalize_linebreaks", "save", "stream", "translate_arxiv_categories",
           "remove_inline_dbg_logs", "print_summary", "REGEX_EMAIL_ADDRESS"]

# Constants
LINUX_NEWLINE = '\n'  # Same for Unix
WINDOWS_NEWLINE = '\r\n'
MAC_NEWLINE = '\r'

# Regular Expression Constants
REGEX_DIGITS = re.compile(r'^[0-9]+$')
REGEX_EMAIL_ADDRESS = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
REGEX_URL = re.compile(r'^(?:(?:https?|ftps?|mailto|gopher|telnet|file):\/\/|www\.|mailto:)\S+')

# Enums
class CrlfFlag(enum.IntFlag):
    """ CRLF Enum Flags """
    Universal = 0x00000
    Linux = 0x00001
    Windows = 0x00002
    MacOSX = 0x00003

class DebugLog(enum.IntFlag):
    """ Specifies what messages to output for the debugging. """
    OFF = 0x00
    ERROR = 0x01
    VERBOSE = 0x80

class Markup(enum.IntFlag):
    """ Markup Enum Flags """
    LaTeX = 0x00000
    HTML = 0x00001
    Wikipedia = 0x00002

# Helper functions
def base36_encode(num: int = 0) -> str:
    """Converts a positive integer into a base36 string
    Adapted from:
    https://en.wikipedia.org/wiki/Base36
    """
    assert num >= 0
    chars = string.digits + string.ascii_uppercase

    res = ''
    while not res or num > 0:
        num, i = divmod(num, 36)
        res = chars[i] + res
    return res


def base36_decode(s: str = "") -> int:
    """Converts a base36 string back to integer"""
    return int(s, 36)

def filesiter(directory: Path, filetype: str ="*.tex", subdirs: bool = False):
    """Returns a recursively yielded generator of all existing files in a specified path

    Args:
        str : The relative or absolute path to the directory to search.
        str : The search string to match against the names of files in path.

    Returns:
        generator class : An generator object containing the full names (including paths) of the files in the directory specified
        by matching the specified search pattern and option.
    """
    if subdirs:
        return directory.rglob(filetype)
    return directory.glob(filetype)

def abspath(path: Path) -> Path:
    """Attempts to resolve absolute path

    Args:
        Path : The relative or absolute path to the directory or file to fix.

    Returns:
        Path: A path object.
    """
    if path.is_absolute() != True:
        if path.is_file():
            path = path.parent.absolute() / path.name
        else:
            path = path.absolute()
    return path


def load_json(filepath: Path) -> dict:
    """ Loads json content from a json file

    Args:
        Path : The relative or absolute path to the directory or file to fix.
    Returns:
        Dict : The JSON data from a json file.
    """
    data = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except OSError as e:
        print(e)
    finally:
        return data

def load_yml(filepath: Path) -> object:
    """ Loads Yaml file

    Args:
        Path : The relative or absolute path to the directory or file to fix.
    """
    yml = None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                yml = yaml.safe_load(f)
            except yaml.YAMLError as ye:
                print(ye)
    except OSError as e:
        print(e)
    finally:
        return yml

def load_pickle(filepath: Path):
    """Loads a picke file

    Args:
        Path : The relative or absolute path to the directory or file to fix.
    """
    data = None
    try:
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
    except IOError as ex:
        print(ex)
    finally:
        return data

def normalize(text: str ="", dedent: bool = True, markup=0) -> str:
    """Removes all leading and trailing white-space characters from the current string object"""

    if isinstance(markup, Markup):
        markup = markup.value

    if markup == Markup.LaTeX:
        text = text.replace('( ', '(')
        text = text.replace(' )', ')')
        text = text.replace(' ,', ',')
        text = text.replace(' .', '.')
        text = text.replace('   ', ' ')
        # text = re.sub(re.compile(r'[ \t]*\n'), r'\n', text)
        text = re.sub(re.compile(r'([ \t]*\n){3,}'), r'\n\n', text)
        text = text.replace(r'\n\n', '\n')
        # text = re.sub(re.compile(r'\n(?!\n)'), r'↵', text)
        # text = re.sub(re.compile(r'\n{3,}'), r'\n\n', text)
        # text = re.sub(re.compile(r'\n+'), r'\n', text)
        # text = re.sub(re.compile(r'↵'), r' ', text)
        # text = re.sub(re.compile(r'  +'), r' ', text)

    # Enforces dedentation but preserves all line breaks
    if dedent:
        text = '\n'.join(line.strip() for line in text.splitlines(True))

    text = text.strip()
    return str(text)

def normalize_linebreaks(text: str = "", flags=0) -> str:
    """Replaces line breaks, between LF, CRLF, and CR, depending on the flag passed.
    Default flag set to Unix / Linux, see: https://www.rfc-editor.org/old/EOLstory.txt
    """
    if isinstance(flags, CrlfFlag):
        flags = flags.value

    text = text.replace(WINDOWS_NEWLINE, LINUX_NEWLINE).replace(
        MAC_NEWLINE, LINUX_NEWLINE)

    if flags == CrlfFlag.Windows:
        text = text.replace(LINUX_NEWLINE, WINDOWS_NEWLINE)
    elif flags == CrlfFlag.MacOSX:
        text = text.replace(LINUX_NEWLINE, MAC_NEWLINE)
    return text

def remove_inline_dbg_logs(text: str = "") -> str:
    """Returns a string cleanned from inline debug logs

    Args:
        text (str): A string of content.
    Returns:
        str: A sanitized string.
    """
    text = re.sub(re.compile(r'\#.*?\.', re.MULTILINE | re.DOTALL), r"\n", text)
    return text

def save(filename: Path, content: str = '', mode: str = 'w', \
    encoding: str = 'utf-8', suffix: str = '.txt', flags=0):
    """Returns a boolean determining if a file was created and its contents written

    Args:
        filename (str): A Filename or a full path to a file.
        content (str): The content to be written to the new file.
        mode (str): Specifies how the operating system should save a file.
        encoding (str): The unicode character ecoding used.
        suffix (str): The suffix to be used for file extension, if any, overrides the original.
        flags (int): CRLF, LF, and CR.
    """

    if isinstance(flags, CrlfFlag):
        newline = _get_crlf_value(flags.value)

    if suffix:
        filename = filename.with_suffix(suffix)

    with open(filename, mode, encoding=encoding, newline=newline) as f:
        f.write(content)

def stream(filename: Path, mode: str = 'rt', encoding: str = 'utf-8', \
    newline=None, readlines=False) -> str:
    """Returns the content of any file

    Args:
        filename: A Filename or a full path to a file.
        mode (str): Specifies how the operating system should open a file.
        encoding (str): The character encoding used.
        newline (str): The newline char (CRLF, LF, CR).
        readlines (bool): Specifices if lines should be read line-by-line.

    Returns:
        string : Raw file contents.
    """
    if isinstance(newline, CrlfFlag):
        newline = _get_crlf_value(newline.value)

    raw = None
    with open(filename, mode, encoding=encoding, newline=newline) as f:
        raw = f.readlines() if readlines else f.read()

    return raw

def detect_encoding(filename: Path) -> str:
    """Gets the current character encoding that the current stream object is using

    Args:
        filename: A Filename or a full path to a file.
    Returns:
        string: The encoding detected.
    """
    encoding = None
    try:
        data = stream(filename, 'rb')
        encoding = "utf-8"
    except UnicodeDecodeError:
        encoding = chardet.detect(data)['encoding']
    finally:
        return encoding

def translate_arxiv_categories(categories: [], lookup: dict):
    """Translates ArXiv Categories to their English form.

    Args:
        categories : Array List, a list containing ArXiv categories.

    Returns:
        A set of translated categories.
    """
    translated = []
    for category in categories:
        if category in translated:
            continue
        try:
            translated.append(lookup[category])
        except KeyError:
            pass

    return translated

def print_summary(total : int = 0, success : int = 0,
    failure : int = 0, log_filename : str = '', activity : str = "") -> None:
    """Prints the summary of a finished activity"""

    now = datetime.utcnow().strftime("%B %d, %Y %I:%M:%S %p")
    print(f"\nPlatform: {platform.system()}\nDate converted: {now}")
    print("-"*56)

    if activity == "single":
        print("1 of 1 files in source folder")
        print(f"Total files successfully coverted: \u001b[2;32;40m{success}")
        print(f"Total files not converted: \u001b[1m\u001b[31m{failure}\n")
    elif activity == "multiple":
        print(f"Total files in source folder: {total}")
        print(f"Total files successfully converted: \u001b[2;32;40m{success}")
        print(f"Total files not converted: \u001b[1m\u001b[31m{failure}\n")
    elif activity == "collection":
        print(f"Total documents in source collection: {total}")
        print(f"Total documents successfully converted: \u001b[2;32;40m{success}")
        print(f"Total documents not converted: \u001b[1m\u001b[31m{failure}\n")

    if failure != 0:
        print(f"\u001b[1m\u001b[31mSee the log, \'{log_filename}\' for more details\nregarding the failed conversions.\n")
    print(f"\u001b[33mNote:The quality of sanitization and conversion varies.")
    print("-"*56)

def _get_crlf_value(flag) -> str:
    """Internal Private: Sets the crlf flag"""
    if flag == CrlfFlag.Windows:
        newline = WINDOWS_NEWLINE
    elif flag == CrlfFlag.MacOSX:
        newline = MAC_NEWLINE
    elif flag == CrlfFlag.Linux:
        newline = LINUX_NEWLINE
    else:
        newline = None

    return newline
