
import os
import re
import sys

FILLERS = set(['uh','um','okay','yes','yeah','oh','heh','yknow','um-huh',
                'uh-uh','uh-huh','uh-hum','mm-hmm'])

from annograph.io.helper import (DiscourseData, AnnotationType,
                            Annotation, BaseAnnotation, find_wav_path)

def phone_match(one,two):
    if one != two and one not in two:
        return False
    return True

def inspect_discourse_multiple_files(word_path, dialect):
    """
    Generate a list of AnnotationTypes for a specified dialect

    Parameters
    ----------
    word_path : str
        Full path to text file
    dialect : str
        Either 'buckeye' or 'timit'

    Returns
    -------
    list of AnnotationTypes
        Autodetected AnnotationTypes for the dialect
    """
    if dialect == 'buckeye':
        annotation_types = [AnnotationType('spelling', 'surface_transcription', None, anchor = True),
                            AnnotationType('transcription', None, 'spelling', base = False, token = False),
                            AnnotationType('surface_transcription', None, 'spelling', base = True, token = True),
                            AnnotationType('category', None, 'spelling', base = False, token = True)]
    elif dialect == 'timit':

        annotation_types = [AnnotationType('spelling', 'transcription', None, anchor = True),
                            AnnotationType('transcription', None, 'spelling', base = True, token = True)]
    else:
        raise(NotImplementedError)
    return annotation_types

def multiple_files_to_data(word_path, phone_path, dialect, annotation_types = None,
                           call_back = None, stop_check = None):
    if annotation_types is None:
        annotation_types = inspect_discourse_multiple_files(word_path, dialect)
    for a in annotation_types:
        a.reset()
    name = os.path.splitext(os.path.split(word_path)[1])[0]

    if call_back is not None:
        call_back('Reading files...')
        call_back(0,0)
    words = read_words(word_path, dialect)
    phones = read_phones(phone_path, dialect)

    data = DiscourseData(name, annotation_types)

    if call_back is not None:
        call_back('Parsing files...')
        call_back(0,len(words))
        cur = 0
    for i, w in enumerate(words):
        if stop_check is not None and stop_check():
            return
        if call_back is not None:
            cur += 1
            if cur % 20 == 0:
                call_back(cur)
        annotations = {}
        word = Annotation(w['spelling'])
        beg = w['begin']
        end = w['end']
        if dialect == 'timit':
            found_all = False
            found = []
            while not found_all:
                p = phones.pop(0)
                if p.begin < beg:
                    continue
                found.append(p)
                if p.end == end:
                    found_all = True
            n = 'transcription'
            level_count = data.level_length(n)
            word.references.append(n)
            word.begins.append(level_count)
            word.ends.append(level_count + len(found))
            annotations[n] = found
        elif dialect == 'buckeye':
            for n in data.base_levels:
                if data[n].token:
                    if w[n] is None:
                        found = [BaseAnnotation('?',w['begin'], w['end'])]
                    else:
                        expected = w[n]
                        found = []
                        while len(found) < len(expected):
                            cur_phone = phones.pop(0)
                            if phone_match(cur_phone.label,expected[len(found)]) \
                                and cur_phone.end >= beg and cur_phone.begin <= end:
                                    found.append(cur_phone)
                            if not len(phones) and i < len(words)-1:
                                print(name)
                                print(w)
                                raise(Exception)
                else:
                    if w[n] is None:
                        found = [BaseAnnotation('?')]
                    else:
                        found = [BaseAnnotation(x) for x in w[n]]
                level_count = data.level_length(n)
                word.references.append(n)
                word.begins.append(level_count)
                word.ends.append(level_count+len(found))
                annotations[n] = found
            for at in annotation_types:
                if at.ignored:
                    continue
                if at.base:
                    continue
                if at.anchor:
                    continue
                value = w[at.name]
                if at.delimited:
                    value = [BaseAnnotation(x) for x in parse_transcription(value)]
                if at.token:
                    word.token[at.name] = value
                else:
                    word.additional[at.name] = value
        annotations[data.word_levels[0]] = [word]
        data.add_annotations(**annotations)
    return data

def load_directory_multiple_files(corpus_context, path, dialect,
                                    annotation_types = None,
                                    feature_system_path = None,
                                    stop_check = None, call_back = None):
    """
    Loads a directory of corpus standard files (separated into words files
    and phones files)

    Parameters
    ----------
    corpus_name : str
        Name of corpus
    path : str
        Path to directory of text files
    dialect : str
        One of 'buckeye' or 'timit'
    annotation_types : list of AnnotationType, optional
        List of AnnotationType specifying how to parse the glosses.
        Auto-generated based on dialect.
    feature_system_path : str, optional
        File path of FeatureMatrix binary to specify segments
    stop_check : callable or None
        Optional function to check whether to gracefully terminate early
    call_back : callable or None
        Optional function to supply progress information during the loading

    Returns
    -------
    SpontaneousSpeechCorpus
        Corpus containing Discourses corresponding to the text files
    """
    if call_back is not None:
        call_back('Finding  files...')
        call_back(0, 0)
    file_tuples = []
    for root, subdirs, files in os.walk(path):
        for filename in files:
            if stop_check is not None and stop_check():
                return
            if not (filename.lower().endswith('.words') or filename.lower().endswith('.wrd')):
                continue
            file_tuples.append((root, filename))
    if call_back is not None:
        call_back('Parsing files...')
        call_back(0,len(file_tuples))
        cur = 0
    for i, t in enumerate(file_tuples):
        if stop_check is not None and stop_check():
            return
        if call_back is not None:
            call_back('Parsing file {} of {}...'.format(i+1, len(file_tuples)))
            call_back(i)
        root, filename = t
        name,ext = os.path.splitext(filename)
        if ext == '.words':
            phone_ext = '.phones'
        else:
            phone_ext = '.phn'
        word_path = os.path.join(root,filename)
        phone_path = os.path.splitext(word_path)[0] + phone_ext
        data = multiple_files_to_data(word_path,phone_path, dialect,
                                        annotation_types,
                                        call_back, stop_check)
        data.wav_path = find_wav_path(word_path)
        corpus_context.add_discourse(data)

    #if feature_system_path is not None:
    #    feature_matrix = load_binary(feature_system_path)
    #    corpus.lexicon.set_feature_matrix(feature_matrix)

def load_discourse_multiple_files(corpus_context, word_path, phone_path, dialect,
                                    annotation_types = None,
                                    lexicon = None,
                                    feature_system_path = None,
                                    stop_check = None, call_back = None):
    """
    Load a discourse from a text file containing interlinear glosses

    Parameters
    ----------
    corpus_name : str
        Informative identifier to refer to corpus
    word_path : str
        Full path to words text file
    phone_path : str
        Full path to phones text file
    dialect : str
        One of 'buckeye' or 'timit'
    annotation_types : list of AnnotationType, optional
        List of AnnotationType specifying how to parse the glosses.
        Auto-generated based on dialect.
    lexicon : Corpus, optional
        Corpus to store Discourse word information
    feature_system_path : str
        Full path to pickled FeatureMatrix to use with the Corpus
    stop_check : callable or None
        Optional function to check whether to gracefully terminate early
    call_back : callable or None
        Optional function to supply progress information during the loading

    Returns
    -------
    Discourse
        Discourse object generated from the text file
    """
    data = multiple_files_to_data(word_path,phone_path, dialect,
                                    annotation_types,
                                    call_back, stop_check)
    data.wav_path = find_wav_path(word_path)
    corpus_context.add_discourse(data)

def read_phones(path, dialect, sr = None):
    output = []
    with open(path,'r') as file_handle:
        if dialect == 'timit':
            if sr is None:
                sr = 16000
            for line in file_handle:

                l = line.strip().split(' ')
                start = float(l[0])
                end = float(l[1])
                label = l[2]
                if sr is not None:
                    start /= sr
                    end /= sr
                output.append(BaseAnnotation(label, begin, end))
        elif dialect == 'buckeye':
            header_pattern = re.compile("#\r{0,1}\n")
            line_pattern = re.compile("\s+\d{3}\s+")
            label_pattern = re.compile(" {0,1};| {0,1}\+")
            f = header_pattern.split(file_handle.read())[1]
            flist = f.splitlines()
            begin = 0.0
            for l in flist:
                line = line_pattern.split(l.strip())
                end = float(line[0])
                label = sys.intern(label_pattern.split(line[1])[0])
                output.append(BaseAnnotation(label, begin, end))
                begin = end

        else:
            raise(NotImplementedError)
    return output

def read_words(path, dialect, sr = None):
    output = list()
    with open(path,'r') as file_handle:
        if dialect == 'timit':
            for line in file_handle:

                l = line.strip().split(' ')
                start = float(l[0])
                end = float(l[1])
                word = l[2]
                if sr is not None:
                    start /= sr
                    end /= sr
                output.append({'spelling':word, 'begin':start, 'end':end})
        elif dialect == 'buckeye':
            f = re.split(r"#\r{0,1}\n",file_handle.read())[1]
            line_pattern = re.compile("; | \d{3} ")
            begin = 0.0
            flist = f.splitlines()
            for l in flist:
                line = line_pattern.split(l.strip())
                end = float(line[0])
                word = sys.intern(line[1])
                if word[0] != "<" and word[0] != "{":
                    citation = line[2].split(' ')
                    phonetic = line[3].split(' ')
                    category = line[4]
                else:
                    citation = None
                    phonetic = None
                    category = None
                if word in FILLERS:
                    category = 'UH'
                line = {'spelling':word,'begin':begin,'end':end,
                        'transcription':citation,'surface_transcription':phonetic,
                        'category':category}
                output.append(line)
                begin = end
        else:
            raise(NotImplementedError)
    return output
