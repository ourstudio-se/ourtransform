import unittest

from ourtransform.framework import (
    Element, Transformer, Mutable, AnyChain, 
    AllChain, Chain, Selector, Process, VerifierRaisedException,
    Level, Verifier,
)
from typing import List, Dict, Callable

class TestFramework(unittest.TestCase):

    def test_tags_can_be_functions_or_objects(self):

        def mut(e, t) -> Element:
            return e

        elements = [
            Element(
                input={"tag_attr": 0},
                tag=lambda x: x.input['tag_attr'],
            ),
            Element(
                input={},
                tag=0,
            ),
            # Infected element
            Element(
                input={},
                tag=lambda x: x['tag_attr'],
            ),
            # Infected element
            Element(
                input={"tag_attr": 0},
                tag=lambda: 0,
            )
        ]

        result = Process(
            selector=Selector(
                chains=[
                    Chain(
                        ordered_events=[
                            Mutable(fn=mut),
                        ],
                        tag=0,
                    ),
                ],
            ),
        ).run(
            elements=elements,
        )

        self.assertEqual(len([e for e in result.elements if len(e.notices) == 0]), 2)
        self.assertEqual(len([e for e in result.elements if len(e.notices) > 0]), 2)

    def test_function_types_when_transform(self):

        def fn_0():
            pass

        def fn_1(elem):
            pass

        def fn_2(elem, meta) -> list:
            return {}

        def fn_3(inp, out, met) -> list:
            return []

        def fn_4(inp, out, met) -> List:
            return []

        def fn_5(inp, out, met) -> List[dict]:
            return []

        def fn_6(inp, out, met) -> [dict]:
            return []

        def fn_7(inp, out, met) -> dict:
            return {}

        def fn_8(inp, out, met) -> Dict[str, int]:
            return {}

        # [
        #    (function: Callable, should_fail: bool), 
        #    ...
        # ]
        fns = [
            (fn_0, True),
            (fn_1, True),
            (fn_2, True),
            (fn_3, False),
            (fn_4, True),
            (fn_5, True),
            (fn_6, True),
            (fn_7, False),
            (fn_8, True),
        ]

        for fn, t in fns:
            if t:
                self.assertRaises(
                    Exception,
                    Transformer,
                    kwargs={
                        "fn":fn,
                    }
                )
            else:
                try:
                    Transformer(fn=fn).do(
                        element=Element(
                            input={},
                        ),
                        meta=None,
                    )
                except Exception as e:
                    self.fail(e)

    def test_function_types_with_mutables(self):

        class MyElement(Element):
            pass

        def fn0():
            pass

        def fn1(elem):
            pass

        def fn2(elem, meta):
            elem.input = []
            return elem

        def fn3(elem, meta) -> Element:
            elem.input = {"a": 1}
            return elem

        def fn4(elem, meta) -> MyElement:
            elem.output = None
            return elem

        # [
        #    (function: Callable, should_fail: bool), 
        #    ...
        # ]
        fns = [
            (fn0, True),
            (fn1, True),
            (fn2, True),
            (fn3, False),
            (fn4, False),
        ]

        for fn, t in fns:
            if t:
                self.assertRaises(
                    Exception,
                    Mutable,
                    kwargs={
                        "fn": fn,
                    },
                )
            else:
                try:
                    Mutable(fn=fn).do(
                        element=Element(
                            input={},
                        ),
                    )
                except Exception as e:
                    self.fail(e)

    def test_changing_output_with_mutables(self):

        def fn(elem, meta) -> Element:
            elem.input["a"] = 0
            elem.output["a"] = 1
            return elem

        element = Element(
            input={"a": 1},
        )
        element.output = {"a": 0}
        try:
            Mutable(
                fn=fn,
            ).do(
                element=element,
            )
        except Exception as e:
            self.fail(e)

    def test_will_succeed_verifier(self):

        def trans_fn(inp, out, met) -> dict:
            return inp

        def ver_fn0(x,y):
            pass

        def ver_fn1(x,y):
            raise VerifierRaisedException("Verifyer did not succeed")

        try:
            Verifier(
                changeable=Transformer(
                    fn=trans_fn,
                ),
                verifier_fn=ver_fn0,
            ).do(
                element=Element(
                    input={},
                )
            )
        
            element = Verifier(
                changeable=Transformer(
                    fn=trans_fn,
                ),
                verifier_fn=ver_fn1,
            ).do(
                element=Element(
                    input={},
                )
            )
            self.assertTrue(element.has_any(levels=[Level.ERROR]))
        except Exception as e:
            self.fail(e)

    def test_will_succeed_chaining(self):

        class NewStruct:
            def __init__(self, d):
                self.d = d

        def mutable_in(e, m) -> Element:
            e.input = {"a": 1}
            return e
        
        def transformer(inp, out, met) -> NewStruct:
            return NewStruct(inp)

        def mutable_out(e, m) -> Element:
            e.output.d = {"b": 88}
            return e

        try:
            element = Chain(
                ordered_events=[
                    Mutable(
                        fn=mutable_in,
                    ),
                    Transformer(
                        fn=transformer,
                    ),
                    Mutable(
                        fn=mutable_out,
                    ),
                ],
                tag="MY_TAG",
            ).do(
                element=Element(
                    input={},
                    tag="MY_TAG",
                )
            )
            self.assertEqual(element.output.d["b"], 88)
            self.assertFalse(element.has_any(levels=[Level.ERROR]))
        except Exception as e:
            self.fail(e)

    def test_will_succeed_multi_chaining(self):

        def mut_fn_fail(e, m) -> Element:
            raise Exception("Did fail!")

        def mut_fn_succ(e, m) -> Element:
            return e

        def trans_fn(i: list, o, m) -> dict:
            return {k: 1 for k in i}

        try:
            element = AnyChain(
                ordered_events=[
                    AllChain(
                        ordered_events=[
                            Mutable(
                                fn=mut_fn_fail,
                            ),
                            Transformer(
                                fn=trans_fn,
                            )
                        ]
                    ),
                    AllChain(
                        ordered_events=[
                            Mutable(
                                fn=mut_fn_succ,
                            ),
                            Transformer(
                                fn=trans_fn,
                            )
                        ]
                    )
                ]
            ).do(
                element=Element(
                    input=["a"],
                )
            )
        except Exception as e:
            self.fail(e)

        self.assertTrue(type(element.input) == list)
        self.assertTrue(type(element.output) == dict)

    def test_will_succeed_type_of_any_chain(self):

        def mutable_in(e, m) -> Element:
            e.input = {"a": 1}
            return e
        
        def mutable_fail(e, m) -> dict:
            return []

        try:
            AnyChain(
                ordered_events=[
                    # Will succeed (which is enough)
                    Mutable(
                        fn=mutable_in,
                    ),
                    # Will fail
                    Mutable(
                        fn=mutable_fail,
                    ),
                ]
            ).do(
                element=Element(
                    input={},
                )
            )
        except Exception as e:
            self.fail(e)

    def test_will_succeed_type_of_all_chain(self):

        def mutable_in(e, m) -> Element:
            e.input = {"a": 1}
            return e
        
        def mutable_fail(e, m) -> dict:
            return []

        try:
            AllChain(
                ordered_events=[
                    Mutable(
                        fn=mutable_in,
                    ),
                    Mutable(
                        fn=mutable_in,
                    ),
                ]
            ).do(
                element=Element(
                    input={},
                )
            )
        except Exception as e:
            self.fail(e)

        self.assertRaises(
            TypeError,
            AllChain(
                ordered_events=[
                    Mutable(
                        fn=mutable_in,
                    ),
                    Mutable(
                        fn=mutable_fail,
                    ),
                ]
            ).do,
            kwargs={
                "element": Element(
                    input={},
                ),
            }
        )

    def test_will_succeed_use_selector(self):

        class NewStruct:
            def __init__(self, d):
                self.d = d

        def mutable_in(e, m) -> Element:
            e.input = {"a": 1}
            return e
        
        def mutable_fail(e, m) -> dict:
            return []

        def transformer(inp, out, m) -> NewStruct:
            return NewStruct(inp)

        def mutable_out(e, m) -> Element:
            e.output.d = {"b": 88}
            return e

        try:
            selector = Selector(
                chains=[
                    AllChain(
                        ordered_events=[
                            Mutable(
                                fn=mutable_in,
                            ),
                            Transformer(
                                fn=transformer,
                            ),
                            Mutable(
                                fn=mutable_out,
                            ),
                        ]
                    ),
                    AnyChain(
                        ordered_events=[
                            Mutable(
                                fn=mutable_in,
                            ),
                            Mutable(
                                fn=mutable_fail,
                            ),
                        ],
                        tag="mytag0"
                    ),
                    AnyChain(
                        ordered_events=[
                            Mutable(
                                fn=mutable_in,
                            ),
                            Mutable(
                                fn=mutable_fail,
                            ),
                        ],
                        tag="mytag1"
                    ),
                ],
            )

            self.assertEqual(
                type(
                    selector.select(
                        element=Element(
                            input={},
                            tag="mytag0"
                        ),
                    ),
                ), 
                AnyChain,
            )
            self.assertEqual(
                type(
                    selector.select(
                        element=Element(
                            input={},
                            tag="mytag1"
                        ),
                    ), 
                ),
                AnyChain,
            )
            self.assertEqual(
                type(
                    selector.select(
                        element=Element(
                            input={},
                        ),
                    ), 
                ),
                AllChain,
            )
        except Exception as e:
            self.fail(e)

    def test_can_execute_transformation_process(self):

        def fn_pre_mutable(element, meta) -> Element:
            return element

        def fn_transform(inp, out, met) -> dict:
            return inp

        def fn_post_mutable(element, meta) -> Element:
            return element
        
        result = Process(
            selector=Selector(
                chains=[
                    Chain(
                        ordered_events=[
                            Mutable(
                                fn=fn_pre_mutable,
                            ),
                        ],
                    )
                ]
            ),
        ).append_subprocess(
            Process(
                selector=Selector(
                    chains=[
                        Chain(
                            ordered_events=[
                                Transformer(
                                    fn=fn_transform,
                                )
                            ]
                        ),
                    ],
                ),
            )
        ).append_subprocess(
            Process(
                selector=Selector(
                    chains=[
                        Chain(
                            ordered_events=[
                                Mutable(
                                    fn=fn_post_mutable,
                                ),
                            ],
                        ),
                    ],
                ),
            )
        ).run([
            Element(
                input={"a": 1},
                tag=None,
            ),
        ])
        self.assertEqual(len(result.elements), 1)
        self.assertEqual(len(result.notices), 0)

    def test_can_compose_process(self):

        def mut_fn_fail(e, m) -> Element:
            raise Exception("Oops!")

        def mut_fn(e, m) -> Element:
            return e

        def trans_fn(i, o, m) -> list:
            return []

        def trans_fn_fail(i, o, m) -> list:
            raise Exception("Oops!")

        result = Process(
            selector=Selector(
                chains=[
                    AllChain(
                        ordered_events=[
                            Selector(
                                chains=[
                                    AllChain(
                                        ordered_events=[
                                            Mutable(fn=mut_fn),
                                            Transformer(fn=trans_fn),
                                        ],
                                    ),
                                    AllChain(
                                        ordered_events=[
                                            Mutable(fn=mut_fn_fail),
                                        ],
                                        tag=0,
                                    ),
                                ],
                            )
                        ]
                    ),
                    AllChain(
                        ordered_events=[
                            Selector(
                                chains=[
                                    AnyChain(
                                        ordered_events=[
                                            Transformer(fn=trans_fn_fail),
                                            Transformer(fn=trans_fn),
                                        ]
                                    )
                                ]
                            )
                        ],
                        tag=99,
                    )
                ]
            )
        ).run(
            elements=[
                Element(
                    input={},
                    tag=99,
                ),
                Element(
                    input={},
                    tag=0, # Should fail
                ),
                Element(
                    input={},
                ),
            ]
        )

        self.assertEqual(len(result.outputs(filter=lambda x: x is None)), 1)
        self.assertEqual(len(result.outputs(filter=lambda x: x is not None)), 2)

    def test_will_not_halt(self):
        """
            There has been problem with Process executing forever. Last
            case was when return type was declared as e.g. [dict]
        """

        def trans_infected_def(i,o,m) -> [dict]:
            return [{}]

        result = Process(
            selector=Selector(
                chains=[
                    AllChain(
                        ordered_events=[
                            AllChain(
                                ordered_events=[
                                    Transformer(fn=trans_infected_def),
                                ]
                            ),
                            Selector(
                                chains=[
                                    AnyChain(
                                        ordered_events=[
                                            Transformer(fn=trans_infected_def),
                                            Transformer(fn=trans_infected_def),
                                        ],
                                        tag=99,
                                    ),
                                ]
                            ),
                            AllChain(
                                ordered_events=[
                                    Transformer(fn=trans_infected_def),
                                ]
                            )
                        ],
                    ),
                ],
            ),
        ).run(
            elements=[
                Element(
                    input={},
                    tag=99,
                ),
                Element(
                    input={},
                    tag=0, # Should fail
                ),
                Element(
                    input={},
                ),
            ]
        )