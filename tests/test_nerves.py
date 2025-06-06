import pytest
from mapknowledge import KnowledgeStore, NERVE_TYPE

store = KnowledgeStore(sckan_version='sckan-2024-09-21')

def test_path_contains_expected_nerves():
    knowledge = store.entity_knowledge('ilxtr:neuron-type-keast-8')
    nerves = set(knowledge.get('nerves', []))
    expected_nerves = {('ILX:0793221', ()), ('ILX:0793220', ())}
    
    assert expected_nerves.issubset(nerves)
    assert len(nerves) == 2

def test_known_nerve_type():
    knowledge = store.entity_knowledge('ILX:0793221')
    assert knowledge.get('type') == NERVE_TYPE

def test_non_nerve_type():
    knowledge = store.entity_knowledge('UBERON:0006448')
    assert knowledge.get('type') != NERVE_TYPE

def test_known_nerve_without_phenotype():
    for term in ['UBERON:0003715', 'ILX:0731969']:
        knowledge = store.entity_knowledge(term)
        assert knowledge.get('type') == NERVE_TYPE

def test_path_having_nerve_without_phenotype():
    test_cases = [
        ('ilxtr:neuron-type-bromo-1', {('UBERON:0003715', ())}),
        ('ilxtr:sparc-nlp/kidney/140', {('ILX:0731969', ())})
    ]
    for path, expected_nerves in test_cases:
        knowledge = store.entity_knowledge(path)
        nerves = set(knowledge.get('nerves', []))
        assert expected_nerves.issubset(nerves)

store.close()
