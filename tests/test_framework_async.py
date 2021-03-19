import numpy as np
import multiprocessing
from unittest import IsolatedAsyncioTestCase
from ourtransform.framework import Process, Selector, AnyChain, Transformer, Element

def transform(i: dict,o,m) -> list:
    return [k for k, v in i.items() if v == 1]

class TestFrameworkAsync(IsolatedAsyncioTestCase):

    async def test_process_run_async_will_succeed(self):
        
        process = Process(
            selector=Selector(
                chains=[
                    AnyChain(
                        ordered_events=[
                            Transformer(fn=transform),
                        ],
                    ),
                ],
            ),
        )
        try:
            result = await process.run_async(
                elements=[
                    Element(input={"a": 0, "b": 1}),
                    Element(input={"c": 0, "y": 1}),
                    Element(input={"d": 1, "b": 0}),
                ]
            )

            self.assertEqual(["b"], result.elements[0].output)
            self.assertEqual(["y"], result.elements[1].output)
            self.assertEqual(["d"], result.elements[2].output)
        except Exception as e:
            self.fail(e)

    async def test_process_run_async_with_timeout(self):

        chars = list("abcdefghijklmno")
        process = Process(
            selector=Selector(
                chains=[
                    AnyChain(
                        ordered_events=[
                            Transformer(fn=transform),
                        ],
                    ),
                ],
            ),
        )
        try:
            await process.run_async(
                elements=[
                    Element(
                        input={
                            np.random.choice(chars): np.random.randint(0, 2) 
                            for _ in range(np.random.randint(1, 10))
                        },
                    )
                    for _ in range(10000)
                ],
                timeout=0.1,
            )
        except Exception as e:
            self.assertEqual(type(e), multiprocessing.TimeoutError)