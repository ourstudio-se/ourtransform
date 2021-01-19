
import unittest
import json

from tests.fake_logger import FakeLogger
from tests.test_transform_subclass import transform_generic, transform_exactly_one
from ourtransform.framework import (Process, Selector, Element, Meta, Mutable, Selector, AllChain, AnyChain, Transformer)
from typing import List

class TestSpecialCaseOne(unittest.TestCase):

    """
        This tests a special case of transforming 
        config rules into constraints.
    """

    def helper_get_elements(self):
        try:
            data = json.load(open("./tests/data/config_rule.json", "r"))
        except:
            print("No config rules in tests/data...")
            return []

        elements = [
            ConfigRuleElement(
                input=data[i],
                tag=data[i]['consequence']['rule_type'],
                id=f"#{i}",
            )
            for i in range(len(data))
        ]
        return elements

    def test_special_case_one(self):
        
        logger = FakeLogger()
        process = Process(
            selector=Selector(
                chains=[
                    AllChain(
                        ordered_events=[
                            Mutable(
                                fn=mute_components_to_strings,
                            ),
                            Transformer(
                                fn=transform_generic,
                            ),
                            Mutable(
                                fn=mute_set_config_meta,
                            )
                        ],
                    ),
                ],
                logger=logger,
            ),
            meta=ConfigGeneralMeta,
        )

        elements = self.helper_get_elements()
        if elements:    
            result = process.run(
                elements=elements,
            )

            for element in result.elements:
                self.assertFalse(element.output is None and len(element.notices) == 0)

        
class ConfigRuleElement(Element):

    def __init__(self, input: dict, tag: str, id: str):
        super(ConfigRuleElement, self).__init__(
            input=input,
            tag=tag,
            id=id,
        )

class ConfigGeneralMeta(Meta):

    support_variable_name   = "#s"
    rule_type_variable_name = "#r"
    id_variable_name        = "#id"
    weight_variables_name   = "#w"
    separator               = "__"


def mute_set_config_meta(e, m: ConfigGeneralMeta) -> ConfigRuleElement:
    for cnst in e.output:
        cnst[m.id_variable_name] = e.id
        cnst[m.rule_type_variable_name] = e.tag
    return e

def mute_components_to_strings(e, m: ConfigGeneralMeta) -> ConfigRuleElement:

    if 'condition' in e.input and 'sub_conditions' in e.input['condition']:
        for sub_condition in e.input['condition']['sub_conditions']:
            sub_condition['components'] = [
                component_to_string(component, m.separator)
                for component in sub_condition['components']
            ]
    e.input['consequence']['components'] = [
        component_to_string(component, m.separator)
        for component in e.input['consequence']['components']
    ]

    return e

def component_to_string(component: dict, separator: str):
    if not ('type' in component and ('code' in component or 'name' in component)):
        raise AttributeError("Missing attributes in component: 'type' or 'code' is missing")

    t = 'type'
    c = 'code' if 'code' in component else 'name'
    
    return separator.join([component[t], component[c]])    

class TestSpecialCaseTwo(unittest.TestCase):
    """
        In this case we'll transform price rules
        into weighted constraints.
    """

    def helper_get_elements(self):
        try:
            data = json.load(open("./tests/data/price_rules.json", "r"))
        except:
            print("No price rules in tests/data...")
            return []
            
        elms = [
            PriceRuleElement(
                inp=data[i],
                tag=data[i]['type'],
                id=data[i]['uid'],
            )
            for i in range(len(data))
        ]
        return elms

    def test_special_case_two(self):

        fake_logger = FakeLogger()
        
        elements = self.helper_get_elements()
        if elements:
            pre_result = Process(
                selector=Selector(
                    chains=[
                        AllChain(
                            ordered_events=[
                                Mutable(
                                    fn=mute_price_rule_components_to_strings,
                                ),
                                Transformer(
                                    fn=transform_price_rule_to_constraints,
                                ),
                                Mutable(
                                    fn=mute_set_id,
                                )
                            ],
                            id="price-rule-conv-chain",
                        )
                    ],
                    logger=fake_logger,
                ),
                meta=ConfigGeneralMeta,
            ).run(
                elements=elements,
            )
            
            self.assertEqual(len(pre_result.notices), 0)

            post_process = Process(
                selector=Selector(
                    chains=[
                        AllChain(
                            ordered_events=[
                                Transformer(
                                    fn=transform_package_price,
                                )
                            ]
                        )
                    ]
                ),
                meta=PreProcessMeta(
                    config_rules={
                        'X': [
                            "Y",
                            "Z",
                        ]
                    },
                    prices=pre_result.outputs(
                        filter=lambda x: x is not None,
                    )
                ),
            ).run(
                pre_result.filter(
                    fn=lambda x: x.output is None,
                )
            )

            not_none_outputs = post_process.outputs(filter=lambda x: x is None)
            self.assertGreater(len(not_none_outputs), 0)


class PriceRuleElement(Element):

    def __init__(self, inp, tag, id):
        super(PriceRuleElement, self).__init__(
            input=inp,
            tag=tag,
            id=id,
        )

class PreProcessMeta:

    cgm = ConfigGeneralMeta

    def __init__(self, config_rules, prices):
        self.config_rules = config_rules
        self.prices = prices

def transform_package_price(i, o, m: PreProcessMeta) -> dict:
    
    for component in i['components']:
        if not "PACKAGE" in component:
            raise Exception("Not a package!")

        price = None
        if component in m.config_rules:
            prices = set()

            for sub_component in m.config_rules[component]:
                for rule in m.prices:
                    if sub_component in rule:
                        prices.add(
                            rule[m.cgm.weight_variables_name],
                        )

            price = i['adjustment'] - sum(prices)

    if price is not None:
        d = {c: 1 for c in i['components']}
        d[m.cgm.weight_variables_name] = price
        d[m.cgm.support_variable_name] = 1
        return d

    raise Exception(f"Price not found for {i['components']}")

def mute_price_rule_components_to_strings(e, m) -> PriceRuleElement:
    
    if 'conditions' in e.input:
        for condition in e.input['conditions']:
            condition['components'] = [
                component_to_string(component, m.separator) 
                for component in e.input['components']
            ]

    e.input['components'] = [
        component_to_string(component, m.separator)
        for component in e.input['components']
    ]

    return e

def mute_set_id(e, m: ConfigGeneralMeta) -> PriceRuleElement:
    e.output[m.id_variable_name] = e.id
    return e


def transform_price_rule_to_constraints(i, o, m) -> dict:

    # Check if this is a package...
    for c in i['components']:
        if "PACKAGE" in c:
            raise Exception("Skip Package!")

    Q = set()
    if 'conditions' in i:
        if len(i['conditions']) > 1:
            raise Exception("Cannot handle conditions lenght > 1")
        
        for condition in i['conditions']:
            Q.update([comp for comp in condition['components']])

    # Q is a set of conjuncted variables
    Q = Q.union(set(i['components']))
    constraint = {k:1 for k in Q}
    constraint[m.support_variable_name] = len(constraint)
    constraint[m.weight_variables_name] = i['adjustment']

    return constraint