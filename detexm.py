# coding=utf-8
# Copyright © The Delatex Authors. All rights reserved.
import sys, multiprocessing
from common import *

arxiv_categories = load_json(json_dir / 'arxiv_categories.json')
text_struct = load_json(data_models / 'text.json')

# Resolve Git
head = current_repo.lookup_reference('HEAD').resolve()
last_commit = current_repo.revparse_single('HEAD^')
current_commit_id = head.target.hex
last_commit_id = last_commit.hex
current_user = current_repo.default_signature.name

# Processing log defaults 
processing_log = load_json(data_models / 'log.json')
processing_log['name'] = 'Delatex 0.3.0'
processing_log['script'] = str(Path(__file__).absolute())
processing_log['git_hash_id'] = current_commit_id
processing_log['user'] = current_user

parser = argparse.ArgumentParser()
parser.add_argument('-db', '--database', nargs='?', type=str)
parser.add_argument('-c', '--collections', nargs='?', type=str)
parser.add_argument('-debug', '--debug', nargs='?', type=bool, default='False', const='False')

group = parser.add_mutually_exclusive_group()
group.add_argument('-m', '--multicore', action='store_true')

def process_arxiv(offset, limit, client, source, destination):
    txtdoc = deepcopy(text_struct)
    proc_log_copy = deepcopy(processing_log)

    ngrams = client[argv.database]
    source = ngrams[source]
    destination = ngrams[destination]
    processing_logs = ngrams['processing_logs']

    projection = {"_id": 1, "title" : 1, "pub_date" : 1, "categories": 1, "raw": 1}
    cursor = source.find({}, projection, no_cursor_timeout=True).skip(offset).limit(limit)

    for doc in cursor:
        
        # Skip if already exists in the destination collection 
        if destination.find_one({'title' : doc.get('title')}):
            continue

        # Extract
        _id = doc.get('_id')
        txtdoc['_source_id'] = doc.get('_id')
        txtdoc['source_corpus_name'] = source.name
        txtdoc['title'] = doc.get('title')
        txtdoc['pub_date'] = doc.get('pub_date')
        txtdoc['keywords'] = translate_arxiv_categories(doc['categories'], arxiv_categories)

        try:
            print(f"Processing document {_id} from collection \'{source.name}\'.", flush=True)
            raw = doc.get('raw')
            text = LaTeX(raw=raw, flags=dbgflag).to_text()
            txtdoc['text'] = text
            result = destination.insert_one(txtdoc)
            inserted_id = result.inserted_id
            proc_log_copy['_source_id'] = inserted_id
        except Exception as ex:
            print(f"Excpetion occured while processing: {_id},\n{ex}", flush=True)
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
        text, raw = "", ""
        
    print("Completed the insertion.", file=sys.stdout, flush=True)
    client.close()


if __name__ == '__main__':
    print("\nDelatex 0.3.1 - convert LaTeX files to plain text.", flush=True)
    print("Copyright 2019 The N-grams Project Authors.\n", flush=True)
    
    # Uncomment for testing purposes:
    #sys.argv = [sys.argv[0], '-db', "ngrams", '-c', "arxiv,texts", '-r', "0,264759", '-debug', "True"]
    #sys.argv = [sys.argv[0], '-s', r"D:\arXiv_TeX_only\0001_001", '-o', r'c:/processed', '-debug', 'True']
    #sys.argv = [sys.argv[0], '-db', "ngrams", '-c', "arxiv,texts", '-debug', "True"]
    
    if len(sys.argv) == 1:
        print("\u001b[1m\u001b[31mNo arguments were provided.")
        parser.print_help()
        sys.exit(0)
    
    argv = parser.parse_args()
    processing_log['args'] = "  ".join(sys.argv[1:])
    dbgflag = DebugLog.ERROR if argv.debug else DebugLog.OFF

    if argv.database:
        if not argv.collections:
            print("Collections argument was missing, -c source, destination.")
            sys.exit(1)

        source, destination = tuple(str(argv.collections).split(","))
        total = 1059035 # The total amount of articles stored. 
        limit = round(total/4 + 0.5)
        skips = range(0, 4*limit, limit) 

        client = mongodb_connection()
        processes = [multiprocessing.Process(target=process_arxiv, \
            args=(n, limit, client, source, destination)) for n in skips]

        for process in processes:
            process.start()

        for process in processes:
            process.join()

    else:
        print("The argument does not match any of the defiened ones, please try again.")
        parser.print_help()
        sys.exit(0)