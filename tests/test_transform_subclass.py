from unittest import TestCase

from tests.fake_logger import FakeLogger
from ourtransform.framework import (
                                    Process, 
                                    Element, 
                                    Selector,
                                    Mutable, 
                                    Transformer, 
                                    Chain, 
                                    AnyChain, 
                                    Meta, 
                                    Level, 
                                    Verifier, 
                                    VerifierRaisedException)

class TestTransformSubclass(TestCase):

    def test_can_transform_subclass(self):
        try:
            logger = FakeLogger()
            ctp = ConfigurationTransformationProcess(
                logger=logger,
            )
            elements = [
                ConfigurationElement(
                    d={"x__a": 1, "b": 1, "0": 1},
                    rule_type="AT_LEAST",
                ),
                ConfigurationElement(
                    d={
                        "condition": {
                            "relation": "ALL",
                            "sub_conditions": [],
                        },
                        "consequence": {
                            "rule_type": "EXACTLY_ONE",
                            "components": ["a", "b", "c"]
                        }
                    },
                    rule_type="EXACTLY_ONE",
                ),
                ConfigurationElement(
                    d={
                        "condition": {
                            "relation": "ALL",
                            "sub_conditions": [
                                {
                                    "relation": "ALL",
                                    "components": ["x", "y"],
                                }
                            ],
                        },
                        "consequence": {
                            "rule_type": "REQUIRES_ALL",
                            "components": ["a", "b", "c"]
                        }
                    },
                    rule_type="EXACTLY_ONE",
                ),
            ]
            result = ctp.run(
                elements=elements,
            )
        except Exception as e:
            self.fail(f"Failed because of error: {e}")

        self.assertGreater(len(result.elements), 0)
        self.assertEqual(len(result.elements_with(notice_levels=[Level.ERROR])), 1)
        self.assertEqual(len(result.notices), 0)
        self.assertEqual(len(result.outputs()), 3)

class ConfigurationElement(Element):

    def __init__(self, d: dict, rule_type: str):
        super(ConfigurationElement, self).__init__(
            input=d,
            tag=rule_type,
        )

class ConfigurationMeta(Meta):

    types = {
        "x": "X",
        "y": "Y",
        "z": "Z",
    }
    support_variable_name = "0"

class ConfigurationTransformationProcess(Process):

    def __init__(self, logger=None):

        super(ConfigurationTransformationProcess, self).__init__(
            selector=Selector(
                chains=[
                    Chain(
                        ordered_events=[
                            Mutable(
                                fn=mute_old_types,
                            ),
                            Mutable(
                                fn=mute_old_types,
                            ),
                            Mutable(
                                fn=mute_old_types,
                            ),
                        ],
                    ),
                    Chain(
                        ordered_events=[
                            Mutable(
                                fn=mute_old_types,
                            ),
                            Mutable(
                                fn=mute_old_types,
                            ),
                        ],
                    ),
                    Chain(
                        ordered_events=[
                            Mutable(
                                fn=mute_old_types,
                            )
                        ],
                        tag="AT_LEAST",
                    ),
                ],
                logger=logger,
            ),
            meta=ConfigurationMeta,
        )

        self.append_subprocess(
            Process(
                selector=Selector(
                    chains=[
                        AnyChain(
                            ordered_events=[
                                Verifier(
                                    changeable=Transformer(
                                        fn=transform_exactly_one,
                                    ),
                                    verifier_fn=verify_transformed_elements,
                                ),
                                Verifier(
                                    changeable=Transformer(
                                        fn=transform_generic,
                                    ),
                                    verifier_fn=verify_transformed_elements,
                                ),
                            ],
                            tag="EXACTLY_ONE",
                        ),
                    ],
                ),
                meta=ConfigurationMeta,
            )
        )

def verify_transformed_elements(element: ConfigurationElement, meta: ConfigurationMeta):
    """
        Verifies transformed elements that succeeded output.
    """
    if not element.output is None:
        if not type(element.output) == list:
            raise VerifierRaisedException("Transformed element must be of type list")

        for output_element in element.output:
            if not type(output_element) == dict:
                raise VerifierRaisedException("Elements in output must be of type dict")

            if not meta.support_variable_name in output_element:
                raise VerifierRaisedException(f"Elements in output must have key {meta.support_variable_name} in them")


def transform_exactly_one(inp: dict, out, met: ConfigurationMeta) -> list:
    """ transform_exactly_one is derived from S, where S is a set of xor'ed variables.
        Due to using a "=" operator, we can use the general formula of
        
        sum_{s in S} s >= 1
        sum_{s in S} -s >= -1    (this constraint is skipped if |S| == 1)
    """
    support_variable_name = met.support_variable_name
    if inp['condition']:
        if inp['condition']['sub_conditions']:
            raise Exception("Rule type 'EXACTLY_ONE' cannot have conditions.")

    constraint_0 = {}
    for component in inp['consequence']['components']:
        constraint_0[component] = 1
    constraint_0[support_variable_name] = 1

    if len(inp['consequence']['components']) == 1:
        return [constraint_0]

    elif len(inp['consequence']['components']) > 1:
        constraint_1 = {}
        for component in inp['consequence']['components']:
            constraint_1[component] = -1
        constraint_1[support_variable_name] = -1

        return [constraint_0, constraint_1]

def transform_generic(inp: dict, out, met: ConfigurationMeta) -> list:

    """ handle_generic is derived from P -> S, where P and S are logic expressions. 
        This function will use a generic method to transform the logic expression P -> S
        into multiple mathematical constraints. This is done by first converting r into
        a logic expression Ç, then Ç is converted into CNF and last into constraints. 
    """
    support_variable_name = met.support_variable_name
    P = None
    if inp['condition'] and inp['condition']['sub_conditions']:
        P = ""
        evaluated_sub_conditions = []
        for sub_condition in inp['condition']['sub_conditions']:
            if sub_condition['relation'] == "ALL":
                concat = " & ".join(sub_condition['components'])
            elif sub_condition.relation == "ANY":
                concat = " | ".join(sub_condition['components'])
            else:
                raise Exception(f"Not implemented for relation type: '{sub_condition.relation}'")

            if not concat == '':
                evaluated_sub_conditions.append(f"({concat})")

        if inp['condition']['relation'] == "ALL":
            P = " & ".join(evaluated_sub_conditions)
        elif inp['condition']['relation'] == "ANY":
            P = " | ".join(evaluated_sub_conditions)
        else:
            raise Exception(f"Not implemented for relation type: '{inp['condition']['relation']}'")

    cmps = inp['consequence']['components']
    if inp['consequence']['rule_type'] in ["REQUIRES_ALL", "PREFERRED"]:
        S = " & ".join(cmps)

    elif inp['consequence']['rule_type'] == "REQUIRES_ANY":
        S = " | ".join(cmps)

    elif inp['consequence']['rule_type'] == "FORBIDS_ALL":
        _cmps = [f"~{x}" for x in cmps]
        S = " & ".join(_cmps)

    elif inp['consequence']['rule_type'] == "REQUIRES_EXCLUSIVELY":

        if P == None:
            return transform_exactly_one(inp=inp, out=out, met=met)

        condition = []
        for i in range(len(cmps)):
            clause = [f"{cmps[j]}" if i == j else f"~{cmps[j]}" for j in range(len(cmps))]
            condition.append(" & ".join(clause))

        S = " | ".join([f"({x})" for x in condition])

    else:
        raise Exception(f"Not implemented for rule type '{inp['consequence']['rule_type']}'")

    expression = S if not P else f"({P}) >> ({S})"
    constraints = fake_expression_to_constraints(
        expression=expression, 
        support_variable_name=support_variable_name,
    )

    _constraints = []
    for constraint, support_vector_value in constraints:
        constraint[support_variable_name] = support_vector_value
        _constraints.append(constraint)

    return _constraints

def mute_old_types(configuration_element: ConfigurationElement, meta: ConfigurationMeta) -> ConfigurationElement:
    
    newinp = {}
    for k,v in configuration_element.input.items():
        
        for t_from, t_to in meta.types.items():
            look_for = f"{t_from}__"
            replace_with = f"{t_to}__"
            if look_for in k:
                k = k.replace(look_for, replace_with)
                break
        
        newinp[k] = v

    configuration_element.input = newinp
    return configuration_element

def fake_expression_to_constraints(expression: str, support_variable_name: str) -> [dict]:
    Q = expression.replace("~", "").split(" >> ")

    def get_vars(Q):
        q = Q.replace('(','').replace(')','')
        if "&" in q:
            return q.split(" & ")
        else:
            return q.split(" | ")

    if len(Q) == 2:
        P, S = Q
        Ps = get_vars(P)
        Ss = get_vars(S)
        d = {
            **{p: -1 for p in Ps},
            **{s: 1 for s in Ss},
        }
        support_vector_value = -len(Ps) + 1
    elif len(Q) == 1:
        Ss = get_vars(S)
        d = {s:1 for s in Ss}
        support_vector_value = 1
    else:
        raise Exception("Cannot compute for expression with neither Q=(S) or Q=(P >> S)")

    return [(d, support_vector_value)]