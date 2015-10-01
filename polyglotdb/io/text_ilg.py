
import os
import re
from collections import Counter

from polyglotdb.exceptions import (DelimiterError, ILGError, ILGLinesMismatchError,
                                ILGWordMismatchError)

from .helper import (compile_digraphs, parse_transcription,
                    DiscourseData, AnnotationType,
                    Annotation, BaseAnnotation, Attribute)

def calculate_lines_per_gloss(lines):
    line_counts = [len(x[1]) for x in lines]
    equaled = list()
    number = 1
    for i,line in enumerate(line_counts):
        if i == 0:
            equaled.append(False)
        else:
            equaled.append(line == line_counts[i-1])
    if False not in equaled[1:]:
        #All lines happen to have the same length
        for i in range(2,6):
            if len(lines) % i == 0:
                number = i
    else:
        false_intervals = list()
        ind = 0
        for i,e in enumerate(equaled):
            if i == 0:
                continue
            if not e:
                false_intervals.append(i - ind)
                ind = i
        false_intervals.append(i+1 - ind)
        counter = Counter(false_intervals)
        number = max(counter.keys(), key = lambda x: (counter[x],x))
        if number > 10:
            prev_maxes = set([number])
            while number > 10:
                prev_maxes.add(number)
                number = max(x for x in false_intervals if x not in prev_maxes)
    return number

def most_frequent_value(dictionary):
    c = Counter(dictionary.values())
    return max(c.keys(), key = lambda x: c[x])

def inspect_discourse_ilg(path, number = None):
    """
    Generate a list of AnnotationTypes for a specified text file for parsing
    it as an interlinear gloss text file

    Parameters
    ----------
    path : str
        Full path to text file
    number : int, optional
        Number of lines per gloss, if not supplied, it is auto-detected

    Returns
    -------
    list of AnnotationTypes
        Autodetected AnnotationTypes for the text file
    """
    trans_delimiters = ['.', ';', ',']
    lines = {}
    if os.path.isdir(path):
        numbers = {}
        for root, subdirs, files in os.walk(path):
            for filename in files:
                if not filename.lower().endswith('.txt'):
                    continue
                p = os.path.join(root, filename)
                lines[p] = text_to_lines(p)
                numbers[p] = calculate_lines_per_gloss(lines[p])
        number = most_frequent_value(numbers)
    else:
        lines[path] = text_to_lines(path)
        number = calculate_lines_per_gloss(lines[path])
        p = path
    annotation_types = []
    for i in range(number):
        name = 'Line {}'.format(i+1)
        if i == 0:
            att = Attribute('spelling','spelling','Spelling')
            a = AnnotationType(name, None, None, anchor = True, token = False, attribute = att)
        else:
            labels = lines[p][i][1]
            cat = Attribute.guess_type(labels, trans_delimiters)
            att = Attribute(Attribute.sanitize_name(name), cat, name)
            a = AnnotationType(name, None, annotation_types[0].name, token = False, attribute = att)
            if cat == 'tier' and a.trans_delimiter is None:
                for l in labels:
                    for delim in trans_delimiters:
                        if delim in l:
                            a.trans_delimiter = delim
                            break
                    if a.trans_delimiter is not None:
                        break
        a.add(lines[p][i][1], save = False)
        annotation_types.append(a)
    for k,v in lines.items():
        if k == p:
            continue
        for i in range(number):
            labels = lines[k][i][1]
            annotation_types[i].add(labels, save = False)

    return annotation_types

def text_to_lines(path):
    delimiter = None
    with open(path, encoding='utf-8-sig', mode='r') as f:
        text = f.read()
        if delimiter is not None and delimiter not in text:
            e = DelimiterError('The delimiter specified does not create multiple words. Please specify another delimiter.')
            raise(e)
    lines = enumerate(text.splitlines())
    lines = [(x[0],x[1].strip().split(delimiter)) for x in lines if x[1].strip() != '']
    return lines

def ilg_to_data(path, annotation_types,
                    stop_check = None, call_back = None):
    #if 'spelling' not in line_names:
    #    raise(PCTError('Spelling required for parsing interlinear gloss files.'))

    lines = text_to_lines(path)

    if len(lines) % len(annotation_types) != 0:
        raise(ILGLinesMismatchError(lines))

    if call_back is not None:
        call_back('Processing file...')
        call_back(0,len(lines))
        cur = 0
    index = 0
    name = os.path.splitext(os.path.split(path)[1])[0]

    for a in annotation_types:
        a.reset()
    data = DiscourseData(name, annotation_types)
    mismatching_lines = list()
    while index < len(lines):
        cur_line = {}
        mismatch = False
        for line_ind, annotation_type in enumerate(annotation_types):
            if annotation_type.name == 'ignore':
                continue
            actual_line_ind, line = lines[index+line_ind]
            if len(cur_line.values()) != 0 and len(list(cur_line.values())[-1]) != len(line):
                mismatch = True

            if annotation_type.delimited:
                line = [parse_transcription(x, annotation_type) for x in line]
            cur_line[annotation_type.name] = line
        if mismatch:
            start_line = lines[index][0]
            end_line = start_line + len(annotation_types)
            mismatching_lines.append(((start_line, end_line), cur_line))
        if len(mismatching_lines) > 0:
            index += len(annotation_types)
            continue
        for word_name in data.word_levels:
            for i, s in enumerate(cur_line[word_name]):
                annotations = {}
                word = Annotation(s)

                for n in data.base_levels:
                    tier_elements = cur_line[n][i]
                    level_count = data.level_length(n)
                    word.references.append(n)
                    word.begins.append(level_count)
                    word.ends.append(level_count + len(tier_elements))
                    annotations[n] = tier_elements
                for line_type in cur_line.keys():
                    if data[line_type].ignored:
                        continue
                    if data[line_type].base:
                        continue
                    if data[line_type].anchor:
                        continue
                    if data[line_type].token:
                        word.token_properties[line_type] = cur_line[line_type][i]
                    else:
                        word.type_properties[line_type] = cur_line[line_type][i]
                annotations[word_name] = [word]
                data.add_annotations(**annotations)
        index += len(annotation_types)

    if len(mismatching_lines) > 0:
        raise(ILGWordMismatchError(mismatching_lines))
    return data


def load_discourse_ilg(corpus_context, path, annotation_types,
                    lexicon = None,
                    feature_system_path = None,
                    stop_check = None, call_back = None):
    """
    Load a discourse from a text file containing interlinear glosses

    Parameters
    ----------
    corpus_context : CorpusContext
        Context manager for the corpus
    path : str
        Full path to text file
    annotation_types : list of AnnotationType
        List of AnnotationType specifying how to parse the glosses.
        Can be generated through ``inspect_discourse_ilg``.
    feature_system_path : str
        Full path to pickled FeatureMatrix to use with the Corpus
    stop_check : callable or None
        Optional function to check whether to gracefully terminate early
    call_back : callable or None
        Optional function to supply progress information during the loading
    """
    data = ilg_to_data(path, annotation_types,
                    stop_check, call_back)
    corpus_context.add_discourse(data)

    #if feature_system_path is not None:
    #    feature_matrix = load_binary(feature_system_path)
    #    discourse.lexicon.set_feature_matrix(feature_matrix)

def load_directory_ilg(corpus_context, path, annotation_types,
                        feature_system_path = None,
                        stop_check = None, call_back = None):
    """
    Loads a directory of interlinear gloss text files

    Parameters
    ----------
    corpus_context : CorpusContext
        Context manager for the corpus
    path : str
        Path to directory of text files
    annotation_types : list of AnnotationType
        List of AnnotationType specifying how to parse the glosses.
        Can be generated through ``inspect_discourse_ilg``.
    feature_system_path : str, optional
        File path of FeatureMatrix binary to specify segments
    stop_check : callable or None
        Optional function to check whether to gracefully terminate early
    call_back : callable or None
        Optional function to supply progress information during the loading
    """
    if call_back is not None:
        call_back('Finding  files...')
        call_back(0, 0)
    file_tuples = []
    for root, subdirs, files in os.walk(path, followlinks = True):
        for filename in files:
            if not filename.lower().endswith('.txt'):
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
            call_back('Parsing file {} of {}...'.format(i+1,len(file_tuples)))
            call_back(i)
        root, filename = t
        name = os.path.splitext(filename)[0]
        load_discourse_ilg(corpus_context, os.path.join(root,filename),
                                    annotation_types, corpus.lexicon,
                                    None,
                                    stop_check, call_back)

    #if feature_system_path is not None:
    #    feature_matrix = load_binary(feature_system_path)
    #    corpus.lexicon.set_feature_matrix(feature_matrix)

def export_discourse_ilg(corpus_context, discourse, path,
                    trans_delim = '.', annotations = None, words_per_line = 10):
    """
    Export a discourse to an interlinear gloss text file, with a maximal
    line size of 10 words

    Parameters
    ----------
    discourse : Discourse
        Discourse object to export
    path : str
        Path to export to
    trans_delim : str, optional
        Delimiter for segments, defaults to ``.``
    """
    if annotations is None:
        raise(Exception('Must specify annotations to output'))
    q = corpus_context.query_graph(corpus_context.word)
    q = q.filter(corpus_context.word.discourse == discourse)
    discourse = q.all()
    with open(path, encoding='utf-8', mode='w') as f:
        line = {x: [] for x in annotations}
        count = 0
        for i, wt in enumerate(discourse):
            count += 1
            for a in annotations:
                line[a].append(wt.r_word.properties[a])
            if i != len(discourse) -1:
                if words_per_line > 0 and count == words_per_line:
                    for a in annotations:
                        f.write(' '.join(line[a]) + '\n')
                    count = 0
                    line = {x: [] for x in annotations}
        if count != 0:
            for a in annotations:
                f.write(' '.join(line[a]) + '\n')
            count = 0
            line = {x: [] for x in annotations}

