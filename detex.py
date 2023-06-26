# coding=utf-8
# Copyright © 2019 Fisnik Hasani. All rights reserved.
# Copyright © 2019 Shai Machnes. All rights reserved.

import multiprocessing
from common import *
import logging.config
from logging.handlers import RotatingFileHandler

# Setup
colorama.init(autoreset=True)
log_filename = "logs/delatex-{:%Y-%m-%d_%H-%M-%S}.log".format(datetime.utcnow())
logging.basicConfig(
    handlers=[RotatingFileHandler(log_filename, maxBytes=60000, backupCount=1)],
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

arxiv_categories = load_json(json_dir / 'arxiv_categories.json')
text_struct = load_json(data_models / 'text.json')
text_struct.pop('significant_parts') # Remove this till we decide
processing_log = load_json(data_models / 'log.json')
processing_log['name'] = 'Delatex 0.3.1'
processing_log['script'] = str(Path(__file__).absolute())

# Resolve Git
head = current_repo.lookup_reference('HEAD').resolve()
last_commit = current_repo.revparse_single('HEAD^')
current_commit_id = head.target.hex
last_commit_id = last_commit.hex
current_user = current_repo.default_signature.name

processing_log['git_hash_id'] = current_commit_id
processing_log['user'] = current_user

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--src')
parser.add_argument('-db', '--database', nargs='?', type=str)
parser.add_argument('-c', '--collections', nargs='?', type=str)
parser.add_argument('-n', '--max', type=int, default=0, help="Number of documents to pull")
parser.add_argument('-debug', '--debug', nargs='?', type=bool, default='False', const='False')
parser.add_argument('-o', '--out', nargs='?', const=None)
parser.add_argument('-p', '--pickle', default="", metavar='FILE')

group = parser.add_mutually_exclusive_group()
group.add_argument('-q', '--quiet', action='store_true')
group.add_argument('-v', '--verbose', action='store_true')
group.add_argument('-m', '--multicore', action='store_true')

# Methods
def delatex(**kwargs):
    """Delatexes La/Tex Markup"""
    # Extract kwargs values:
    source = kwargs.get('source', None)
    destination = kwargs.get('destination', "texts_tmp")
    total = kwargs.get('total', 0)
    limit = kwargs.get('limit', None)
    skip = kwargs.get('skip', None)

    txtdoc = deepcopy(text_struct)
    proc_log_copy = deepcopy(processing_log)
    success = failure = 0
    processing_logs = ngrams['processing_logs']

    # Fields we want
    projection = {"_id": 1, "document_id": 1, "title" : 1, "pub_date" : 1, "categories": 1, "raw": 1}

    if skip:
        cursor = source.find({}, projection, no_cursor_timeout=True).skip(skip).limit(limit)
    else:
        pass

    for i, doc in enumerate(cursor, 1):

        # Skip if already exists in the destination collection
        if destination.find_one({'title' : doc.get('title')}):
            continue

        # Extract
        _id = doc.get('_id')
        txtdoc['_id_at_source_corpus'] = doc.get('_id')
        txtdoc['source_corpus_name'] = source.name
        txtdoc['document_id'] = doc.get('document_id')
        txtdoc['title'] = doc.get('title')
        txtdoc['pub_date'] = doc.get('pub_date')
        txtdoc['keywords'] = translate_arxiv_categories(doc['categories'], arxiv_categories)

        try:
            print(f"Processing: {i}/{total} documents from collection \'{source.name}\'.", file=sys.stdout, flush=True)
            logging.info(f"Processing document {_id} from collection \'{source.name}\'.")
            raw = doc.get('raw')
            text = LaTeX(raw=raw, flags=dbgflag).to_text()
            txtdoc['text'] = text
            result = destination.insert_one(txtdoc)
            proc_log_copy['_source_id'] = result.inserted_id
            success += 1
        except Exception as ex:
            logging.exception(f"Excpetion occured while processing: {_id},\n{ex}", exc_info=True)
            failure += 1
            txtdoc = proc_log_copy = {}
            txtdoc = deepcopy(text_struct)
            proc_log_copy = deepcopy(processing_log)
            continue

        proc_log_copy['retrieved_from_source_at'] = datetime.utcnow().isoformat()
        proc_log_copy['converted_at'] = datetime.utcnow().isoformat()
        proc_log_copy['created_at'] = datetime.utcnow().isoformat()
        processing_logs.insert_one(proc_log_copy)

        # Reset
        txtdoc = proc_log_copy = {}
        txtdoc = deepcopy(text_struct)
        proc_log_copy = deepcopy(processing_log)
        text = raw = ""

    else:
        print_summary(total, success, failure, "collection")


if __name__ == '__main__':
    print("\nDelatex 0.3.1 - convert LaTeX files to plain text.", flush=True)
    print("Copyright 2019 The N-grams Project Authors.\n", flush=True)
    
    # Uncomment for testing purposes:
    # sys.argv = [sys.argv[0], '-db', "ngrams", '-c', "arxiv,", '-n', '3', '-debug', "True"]
    # sys.argv = [sys.argv[0], '-db', "ngrams", '-c', "arxiv,texts_tmp", '-debug', "True", '-m']
    # sys.argv = [sys.argv[0], '-s', r"D:\arXiv_TeX_only\0001_001", '-o', r'c:/processed', '-debug', 'True']
    
    if len(sys.argv) == 1:
        print("\u001b[1m\u001b[31mNo arguments were provided.")
        parser.print_help()
        sys.exit(0)

    argv = parser.parse_args()
    processing_log['args'] = "  ".join(sys.argv[1:])
    dbgflag = DebugLog.ERROR if argv.debug else DebugLog.OFF
    multicore = True if argv.multicore else False

    if argv.database:
        if not argv.collections:
            print("Collections argument was missing, -c source, destination.")
            sys.exit(1)

        n = argv.max
        source_name, destination_name = tuple(str(argv.collections).split(","))

        client = mongodb_connection()
        ngrams = client[argv.database]
        source = ngrams[source_name]

        if destination_name not in ngrams.list_collection_names():
           ngrams.create_collection(name=destination_name)
        destination = ngrams[destination_name]

        # Fields we want
        projection = {"_id": 1, "document_id": 1, "title" : 1, "pub_date" : 1, "categories": 1, "raw": 1}

        if multicore is not True:
            # Invoke delatexing
            if not destination:
               delatex(source=source, total=n)
            delatex(source=source, destination=destination, total=n)
        else:
            total = client[argv.database][source].count() # The total amount of articles stored.
            limit = round(total/4 + 0.5)
            skips = range(0, 4*limit, limit)

            processes = [multiprocessing.Process(target=delatex, \
            kwargs={'skip' : skip, 'limit' : limit, 'source' : source, 'destination' : destination}) for skip in skips]

            for process in processes:
                process.start()

            for process in processes:
               process.join()


        client.close()
        gc.enable()
        gc.collect()

    elif argv.pickle:
        pickle = abspath(Path(argv.pickle))
        print('\u001b[33m' + f"Loading pickle file: {pickle.name}")
        pickle_data = load_pickle(pickle)

        if not argv.src:
            print("Source diectory is missing, use -s \'directory path\'")
            sys.exit(1)
        src = abspath(Path(argv.src))

        if not argv.out:
            out = src.parent

        if pickle_data:
            for v in pickle_data.values():
                tex = namedtuple('tex', v.keys())(*v.values())
                if tex.do_have_TeX:
                    for f in filesiter(src / tex.folder):
                        try:
                            raw = stream(f, 'rt')
                            text = LaTeX(raw=raw, flags=dbgflag).to_text()
                            inf, outf = f.name, f.name[:-3] + "txt"
                            if save(out, text, flags=CrlfFlag.Linux):
                                print(f"{outf} was sanitized and saved.", file=sys.stdout)
                            else:
                                print(f"\u001b[31m{inf} was not sanitized and saved.", file=sys.stderr)
                        except Exception as ex:
                                print(f"\u001b[31m{ex}", file=sys.stderr, flush=True)
        else:
            raise Exception("Error! The pickle file could not be loaded, aborting.", file=sys.stderr)
    elif argv.src:
        dirs_exist = False
        src = abspath(Path(argv.src))
        out = abspath(Path(argv.out))
        if not out:
            out = src.parent

        if isinstance(src, Path) and isinstance(out, Path):
            if (src.exists() and out.exists()):
                if src.is_file():
                    if not (src.suffix == '.tex'):
                        raise ValueError(f"\u001b[1m\u001b[31mExpects *.tex file extension, but was given *{src.suffix}")
                    try:
                        inf, outf = src.name, src.name[:-3] + "txt"
                        print(f"\u001b[1m\u001b[33mProcessing: {src.name}")
                        raw = stream(src, 'rt', encoding=detect_encoding(src))
                        text = LaTeX(raw=raw, flags=dbgflag).to_text()
                        if save(str(out / outf), text, 'wt', flags=CrlfFlag.Linux):
                            print(f"\u001b[2;32;40m{outf} was sanitized and saved.", file=sys.stdout)
                        else:
                            print(f"{inf} was not sanitized and saved.", file=sys.stderr, flush=True)
                    except Exception as ex:
                        print(f"\u001b[1m\u001b[31m{ex}", file=sys.stderr, flush=True)

                else:
                    total = sum(1 for f in filesiter(src, filetype="*.tex", subdirs=False))
                    i = 1
                    success = failure = 0
                    print("Initilaizing multi-processing of *.tex files.", flush=True)
                    for f in filesiter(src, filetype="*.tex", subdirs=False):
                        try:
                            inf, outf = f.name, f.name[:-3] + "txt"
                            print(f'Processing: {i}/{total} files.', file=sys.stdout, flush=True)
                            logging.info(f"Processing \'{f}\' file.")
                            raw = stream(f, 'rt', encoding=detect_encoding(f))
                            text = LaTeX(raw=raw, flags=dbgflag).to_text()
                            save(out / outf, text, 'wt', flags=CrlfFlag.Linux)
                            success += 1
                            i += 1
                        except UnicodeDecodeError as dex:
                            logging.exception(dex)
                            failure += 1
                            i += 1
                            continue # Skip this file.
                        except KeyboardInterrupt as kex:
                            print(f"\u001b[1m\u001b[31mProcess interrupted by Ctrl+C.")
                            logging.exception(kex)
                            print_summary(total, success, failure, "multiple")
                            sys.exit(0)
                        except Exception as ex:
                            logging.exception(f"An excpetion occured while processing: {inf},\n{ex}", exc_info=True)
                            failure += 1
                            i += 1
                    else:
                        print_summary(total, success, failure, "multiple")
            else:
                raise Exception("\u001b[1m\u001b[31mError! None of the directories exists.")
    else:
        print("The argument does not match any of the defiened ones, please try again.")
        parser.print_help()
        sys.exit(0)
