# OurTransform Package

This is a package transforms elements from one data structure to another. 

## Installation
Use the package manager [pip](https://pip.pypa.io/en/stable/) to install
```bash
pip install ourtransform
```
## Usage
The `ourtransform` python package is a framework for changing and transforming data from one data structure to another, in a simple a structured way. In this documentation, we will provide the how-to by an example. We are given a set of combinatorial rules and want them to be transformed into linear halfspaces. All functionality is based on the class `Element`, which is the atomic object of `ourtransform` framework. 


#### Element
We start of by defining our `Element` as a sub class. The `tag` field can be useful to direct elements to a specific event.

```python
from ourtransform.framework import Element

class MyElement(Element):

    def __init__(self, rule: dict):
        super(MyElement, self).__init__(
            input=rule,
            tag=lambda element: element.input["ruleType"],
        )
```

Now we want to compose our transforming process, but before we introduce some of the key feature classes.

#### Transformer
A `Transformer`'s, sub class to `Changeable`, job is to *transform* from one data type to another. In this case, we want to take the input data and turn it in to a list of dictionaries. A `Transformer` **must** take three inputs: input, output and meta. The input is the input of the element, output the output and meta any other information needed to perform the transformation. The output is passed along since there might been done an earlier transformation that needs to be taken into consideration. 

```python

conjunction_rule_transformer = Transformer(
    fn=transform_conjunction_rule_to_constraint, 
    id="transform_conjunction_rule_to_constraint",
)

def transform_conjunction_rule_to_constraint(_input: dict, _output: list, meta: Meta) -> dict:

    if _output is None and "variables" in _input:
        # Here we'll create one dict were each variable
        # in "variables" is set to -1
        _output = {c: -1 for c in _input["variables"]}
        # The support vector in a linear halfspace should in this case be
        # equal to the number of variables
        _output['b'] = -len(_output)
    
    return _output

disjunction_rule_transformer = Transformer(
    fn=transform_disjunction_rule_to_constraint, 
    id="transform_disjunction_rule_to_constraint",
)

def transform_disjunction_rule_to_constraint(_input: dict, _output: list, meta: Meta) -> dict:

    if _output is None and "variables" in _input:
        # Here we'll create one dict were each variable
        # in "variables" is set to -1
        _output = {c: -1 for c in _input["variables"]}
        # The support vector in a linear halfspace should in this case be
        # equal to -1, allowing for at least one variable to be set
        _output['b'] = -1
    
    return _output

```

#### Mutable
A `Mutable`'s, sub class to `Changeable`, job is to *change* the actual data of the input or output. It can be used as some preprocessing before actually transforming the data or postprocessing after transformation has been done. A `Mutable` **must** take two arguments: element (instance of `Element`) and meta. It must also return the same `Element` that was given.

```python

mutable = Mutable(
    fn=concatenate_type_and_name, 
    id="#id0",
)

def concatenate_type_and_name(element: MyElement, meta: Meta) -> MyElement:

    # Do stuff with input...
    if "variables" in element.input and isinstance(element.input["variables"], list):
        # A variable will go from e.g. {"type": "type", "name": "name"} to "typename".
        element.input["variables"] = [f"{c['type']}{c['name']}" for c in element.input["variables"]]

    return element

```

#### Chain(s)
A `Chain` is a series of events that can be composed in different ways. There are mainly two ways chaining. The first is using the sub class `AllChain`, which requires all events to be performed, and the second is using the sub class `AnyChain`, which requires at least one of the events to be performed.

```python
# Define the chain
simple_all_chain = AllChain(
    ordered_events=[
        Mutable(fn=...),
        Transformer(fn=...),
    ],
)
```
The `simple_all_chain` will (when run) do the Mutable first, and then do the Transfomer. If any of them fails, the ``AllChain`` will fail as well. 

```python
# Define the chain
simple_any_chain = AnyChain(
    ordered_events=[
        Mutable(fn=...),
        Transformer(fn=...),
    ],
)
```
The `simple_any_chain` will (when run) just as the `AllChain` do the Mutable first, and then do the Transformer. However, if one of them succeeds, the `AnyChain` also succeeds. Before proceeding with our example, we'll introduce one key class feature first.

#### Selector
The `Selector` is an Event that directs an element to a chain. Every Chain and Element are enabled with an optional tag the Selector is using. Let's continue from the example above where we had two transformers. We'd like the rules tagged with "conjunction" to be processed by `transform_conjunction_rule_to_constraint`, and the rules tagged with "disjunction" to be processed by `transform_disjunction_rule_to_constraint`. However, before processing with any of these transformers we want to change the input data using the mutable above. The following code has two AllChains. The first one grabs the Elements tagged with "conjunction" and the second one with "disjunction". Both are then running the Mutable -function `concatenate_type_and_name`, followed by their transformer.

```python
# Define the chain
selector = Selector(
    chains=[
        AllChain(
            ordered_events=[
                Mutable(fn=concatenate_type_and_name),
                Transformer(fn=transform_conjunction_rule_to_constraint),
            ],
            tag="conjunction",
        ),
        AllChain(
            ordered_events=[
                Mutable(fn=concatenate_type_and_name),
                Transformer(fn=transform_disjunction_rule_to_constraint),
            ],
            tag="disjunction",
        ),
    ],
)
```

Now we could run a list of Elements and transforming them from rules to linear halfspaces, represented as dictionaries:
```python

elements = [
    MyElement(
        rule={
            "ruleType": "conjunction",
            "variables": ["p", "q"],
        },
    ),
    MyElement(
        rule={
            "ruleType": "disjunction",
            "variables": ["x", "y"],
        },
    ),
    MyElement(
        rule={
            "ruleType": "disjunction",
            "variables": ["p", "y"],
        },
    ),
]

for element in elements:
    # Process each element with the selector...
    processed = selector.do(
        element=element,
    )

```

#### Process
There is one class to hold it all together and make the transformation of elements easy to process and that's the e Process class. It takes a Selector as input and then is run by using the `run` function.

```python
process = Process(
    selector=Selector(
        chains=[
            AllChain(
                ordered_events=[
                    Mutable(...),
                    Mutable(...),
                    Transformer(...),
                ],
            ),
        ],
    ),
)

result = process.run(
    elements=elements,
)
```

Run `async` with multiprocessing by `run_async`. Set a timeout to limit for how long it can run. It will throw an `TimeoutError` if not completed.

```python

result = await process.run_async(
    elements=elements,
    timeout=600,
)
```

A Process can compute sub processes by using the `append_subprocess(process=...)` and then run it. It will then compute itself first and pass on the result to the sub process.

```python
process_main = Process(
    selector=Selector(
        chains=[
            AllChain(
                ordered_events=[
                    Mutable(...),
                    Mutable(...),
                    Transformer(...),
                ],
            ),
        ],
    ),
).append_subprocess(
    process=Process(selector=...),
)

result = process.run(
    elements=elements,
)
```
#### Verifier
A Verifier is a type of Event that verifies the result from a `Changeable`. 

```python
def transform(i, o, m) -> dict:
    return {"a": 1, "b": 0}

def verifier(e, m):
    if isinstance(e.output, dict):
        raise Exception(f"Element {e} must be of type {dict}!")

    for k,v in e.output.items():
        if v == 0:
            raise Exception(f"Output of element cannot have zeros: key {k}")

verifier = Verifier(
    changeable=Transformer(
        fn=transform,
    ),
    verifier_fn=verifier,
)
```
## Contributing and todo's
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
Please make sure to update tests as appropriate.

## License
[MIT](https://choosealicense.com/licenses/mit/)