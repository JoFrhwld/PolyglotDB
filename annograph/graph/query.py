
from .elements import ContainsClauseElement

from .func import Count

class GraphQuery(object):
    def __init__(self, graph, to_find):
        self.graph = graph
        self.to_find = to_find
        self._criterion = []
        self._contained_by_annotations = set()
        self._contains_annotations = set()
        self._left_aligned_criterion = []
        self._right_aligned_criterion = []
        self._additional_columns = []
        self._order_by = []
        self._group_by = []
        self._aggregate = []

    def filter(self, *args):
        self._criterion.extend(args)
        return self

    def filter_contains(self, *args):
        args = [ContainsClauseElement(x.attribute, x.value) for x in args]
        self._criterion.extend(args)
        annotation_set = set(x.attribute.annotation for x in args)
        self._contains_annotations.update(annotation_set)
        return self

    def filter_contained_by(self, *args):
        self._criterion.extend(args)
        annotation_set = set(x.attribute.annotation for x in args)
        self._contained_by_annotations.update(annotation_set)
        return self

    def filter_left_aligned(self, annotation_type):
        self._left_aligned_criterion.append(annotation_type)
        return self

    def filter_right_aligned(self, annotation_type):
        self._right_aligned_criterion.append(annotation_type)
        return self

    def cypher(self):
        kwargs = {'corpus_name': self.graph.corpus_name,
                    'preceding_condition': '',
                    'relationship_type_alias':self.to_find.rel_alias,
                    'begin_node_alias': self.to_find.begin_alias,
                    'end_node_alias': self.to_find.end_alias,
                    'following_condition': '',
                    'additional_match': '',
                    'additional_where': '',
                    'additional_columns': '',
                    'order_by': ''}
        if self._aggregate:
            template = '''MATCH {preceding_condition}({begin_node_alias})-[{relationship_type_alias}]->({end_node_alias}){following_condition}{additional_match}
                    WHERE {begin_node_alias}.corpus = '{corpus_name}'
                    {additional_where}
                    RETURN {aggregates}{additional_columns}{order_by}'''
            properties = []
            for g in self._group_by:
                properties.append(g.aliased_for_output())
            for a in self._aggregate:
                properties.append(a.for_cypher())
            kwargs['aggregates'] = ', '.join(properties)

        else:
            template = '''MATCH {preceding_condition}({begin_node_alias})-[{relationship_type_alias}]->({end_node_alias}){following_condition}{additional_match}
                    WHERE {begin_node_alias}.corpus = '{corpus_name}'
                    {additional_where}
                    RETURN DISTINCT {relationship_alias}{additional_columns}{order_by}'''
            kwargs['relationship_alias'] = self.to_find.alias

        properties = []
        annotation_set = set()
        for c in self._criterion:
            properties.append(c.for_cypher())

            annotation_set.add(c.attribute.annotation)
            try:
                annotation_set.add(c.value.annotation)
            except AttributeError:
                pass

        if properties:
            kwargs['additional_where'] += '\nAND ' + '\nAND '.join(properties)

        to_add = sorted((x for x in annotation_set if x.type == self.to_find.type), key = lambda x: x.pos)
        prec_template = '''({b_name})-[{name}]->'''
        foll_template = '''-[{name}]->({e_name})'''
        if to_add:
            current = to_add[0].pos
            for a in to_add:
                if a.pos == 0:
                    current += 1
                    continue
                if a.pos < 0:
                    while a.pos != current:
                        b_name = self.to_find.begin_template.format(self.to_find.type,current)
                        kwargs['preceding_condition'] += prec_template.format(name = ':{}'.format(self.to_find.type),
                                                            b_name = b_name)
                        current += 1
                    kwargs['preceding_condition'] += prec_template.format(name = a.rel_alias, b_name = a.begin_alias)
                elif a.pos > 0:
                    while a.pos != current:
                        e_name = self.to_find.end_template.format(self.to_find.type, current)
                        kwargs['following_condition'] += foll_template.format(name = ':{}'.format(self.to_find.type),
                                                            e_name = e_name)
                        current += 1
                    kwargs['following_condition'] += foll_template.format(name = a.rel_alias, e_name = a.end_alias)
                current += 1

        #other_to_finds = [x for x in annotation_set if x.type != self.to_find.type]
        #for o in other_to_finds:
        #    if o.pos == 0:
        #        self._contained_by_annotations.add(o)

        left_align_template = '''()<-[:{align_type}]-({begin_node_alias})'''
        right_align_template = '''()-[:{align_type}]->({end_node_alias})'''
        for la in self._left_aligned_criterion:
            match_string = left_align_template.format(align_type = la.type,
                                begin_node_alias = self.to_find.begin_alias)
            kwargs['additional_match'] += ',\n' + match_string
        for ra in self._right_aligned_criterion:
            match_string = right_align_template.format(align_type = ra.type,
                                end_node_alias = self.to_find.end_alias)
            kwargs['additional_match'] += ',\n' + match_string

        contained_by_template = '''({begin_node_alias})<-[:{annotation_type}*0..]-({containing_begin})-[{relationship_type_alias}]->({containing_end})<-[:{annotation_type}*0..]-({end_node_alias})'''
        for a in self._contained_by_annotations:
            match_string = contained_by_template.format(annotation_type = self.to_find.type,
                                                relationship_type_alias = a.rel_alias,
                                                containing_begin = a.begin_alias,
                                                containing_end = a.end_alias,
                                                begin_node_alias = self.to_find.begin_alias,
                                                end_node_alias = self.to_find.end_alias)
            kwargs['additional_match'] += ',\n' + match_string

        contains_template = '''({begin_node_alias})-[{relationship_type_alias}*0..]->({end_node_alias})'''
        for a in self._contains_annotations:
            match_string = contains_template.format(relationship_type_alias = a.rel_alias,
                                begin_node_alias = self.to_find.begin_alias,
                                end_node_alias = self.to_find.end_alias)
            kwargs['additional_match'] += ',\n' + match_string

        properties = []
        for c in self._order_by:
            if c[0] not in set(self._additional_columns):
                self._additional_columns.append(c[0])
            element = c[0].output_alias
            if c[1]:
                element += ' DESC'
            properties.append(element)

        if properties:
            kwargs['order_by'] += '\nORDER BY ' + ', '.join(properties)

        properties = []
        for c in self._additional_columns:
            properties.append(c.aliased_for_output())
        if properties:
            kwargs['additional_columns'] += ', ' + ', '.join(properties)
        query = template.format(**kwargs)

        return query

    def group_by(self, field):
        self._group_by.append(field)
        return self

    def order_by(self, field, descending = False):
        self._order_by.append((field, descending))
        return self

    def times(self, begin_name = None, end_name = None):
        if begin_name is not None:
            self._additional_columns.append(self.to_find.begin.column_name('begin'))
        else:
            self._additional_columns.append(self.to_find.begin)
        if end_name is not None:
            self._additional_columns.append(self.to_find.end.column_name('end'))
        else:
            self._additional_columns.append(self.to_find.end)
        return self

    def duration(self):
        self._additional_columns.append(self.to_find.duration.column_name('duration'))
        return self

    def all(self):
        return self.graph.graph.cypher.execute(self.cypher())

    def count(self):
        self._aggregate = [Count()]
        cypher = self.cypher()
        value = self.graph.graph.cypher.execute(cypher)
        return value.one

    def aggregate(self, *args):
        self._aggregate = args
        cypher = self.cypher()
        value = self.graph.graph.cypher.execute(cypher)
        return value