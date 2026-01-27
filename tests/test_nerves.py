import pytest
from mapknowledge import NERVE_TYPE

def test_path_contains_expected_nerves(store):
    knowledge = store.entity_knowledge('ilxtr:neuron-type-keast-8')
    nerves = set(knowledge.get('nerves', []))
    expected_nerves = {('ILX:0793221', ()), ('ILX:0793220', ())}
    assert expected_nerves.issubset(nerves)
    assert len(nerves) == 2

def test_known_nerve_type(store):
    knowledge = store.entity_knowledge('ILX:0793221')
    assert knowledge.get('type') == NERVE_TYPE

def test_non_nerve_type(store):
    knowledge = store.entity_knowledge('UBERON:0006448')
    assert knowledge.get('type') != NERVE_TYPE

@pytest.mark.parametrize("term", ['UBERON:0003715', 'ILX:0731969'])
def test_known_nerve_without_phenotype(store, term):
    knowledge = store.entity_knowledge(term)
    assert knowledge.get('type') == NERVE_TYPE

@pytest.mark.parametrize(
    "path,expected_nerves",
    [
        ('ilxtr:neuron-type-bromo-1', {('UBERON:0003715', ())}),
        ('ilxtr:sparc-nlp/kidney/140', {('ILX:0731969', ())}),
    ],
)

def test_path_having_nerve_without_phenotype(store, path, expected_nerves):
    knowledge = store.entity_knowledge(path)
    nerves = set(knowledge.get('nerves', []))
    assert expected_nerves.issubset(nerves)
