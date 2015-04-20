import os
import pytest

from annograph.classes import Corpus

from annograph.config import session_scope

from annograph.utils import plot_graph

from annograph.io import add_discourse

def test_plot_corpus_untimed(test_dir, corpus_data_untimed, show_plots):
    c = Corpus('sqlite:///'+ os.path.join(test_dir,'generated','test_untimed.db'))
    c.initial_setup()
    add_discourse(c, corpus_data_untimed[0])

    plot_graph(c, show = show_plots, output = os.path.join(test_dir, 'generated','untimed.dot'))

def test_plot_corpus_syllable_morpheme(test_dir, corpus_data_syllable_morpheme, show_plots):
    c = Corpus('sqlite:///'+ os.path.join(test_dir,'generated','test_untimed.db'))
    c.initial_setup()
    add_discourse(c, corpus_data_syllable_morpheme[0])

    plot_graph(c, show = show_plots, output = os.path.join(test_dir, 'generated','syllable_morpheme.dot'))

def test_plot_corpus_ur_sr(test_dir, corpus_data_ur_sr, show_plots):
    c = Corpus('sqlite:///'+ os.path.join(test_dir,'generated','test_untimed.db'))
    c.initial_setup()
    add_discourse(c, corpus_data_ur_sr[0])

    plot_graph(c, show = show_plots, output = os.path.join(test_dir, 'generated','ur_sr.dot'))
