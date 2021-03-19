import abc
import copy
from enum import Enum
from functools import partial
from inspect import signature
from ourtransform.utils import distribute
from multiprocessing import Pool, cpu_count
from typing import Any, List, Dict, Callable

class Level(str, Enum):
    """
    Level of a notice.
    """

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class Notice(object):
    """
    A notice is a weighted message. The weight is set
    by adding a level to the notice.
    """
    
    def __init__(self, msg: str, level: Level):
        self.msg = msg
        self.level = level

    def __hash__(self):
        return hash(f"{self.msg}{self.level}")

    def __eq__(self, other):
        # another object is equal to self, iff 
        # it is an instance of MyClass
        return self.__hash__() == other.__hash__()

class Element(object):
    """
    An element is the object that holds input and output data. 
    It is the core of any transformation system.
    """
    def __init__(self, input: Any, tag: Any = None, id: str = None):
        self.id = id
        self.input = input
        self.output = None
        self._tag = tag
        self.notices = set()

    def has_any(self, levels: Level):
        for n in self.notices:
            if n.level in levels:
                return True
        return False

    @property
    def tag(self):
        if callable(self._tag):
            try:
                _tag = self._tag(self)
            except Exception as e:
                e = Exception(f"Tag of element {type(self)} could not be resolved: {e}")
                self.notices.add(
                    Notice(
                        msg=str(e),
                        level=Level.ERROR,
                    )
                )
                raise e
        else:
            _tag = self._tag
        return _tag

class Meta(object):
    """
    Meta is any data that is pushed into a Changeable, along with an Element.
    """
    pass

class Event(object):
    """
    Event is an abstract class to represent type of classes
    that all share certain methods, such as do.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def do(self, element: Element, meta: Meta = None):
        raise NotImplementedError()

class Changeable(Event):
    """
    A Changeable is a class that will change data from some way to another
    """

    def __init__(self, fn: Callable, id: str = None):
        self.__verify_fn__(fn)
        self.fn = fn
        self.id = id

    def do(self, element: Element, meta: Meta = None):
        """
            Do chaining of given element. Meta data is optional.
            
            Args: (Element) element, (Meta) meta = None
            Return: Element
        """
        raise NotImplementedError()

    def __verify_fn__(self, fn: Callable):
        raise NotImplementedError()

    @staticmethod
    def __verify_fn_output__(fn: Callable, output: Any):
        """
            Verify return type of fn such that the output has same type.
        """
        expected_output_type = signature(fn).return_annotation
        actual_output_type = type(output)
        try:
            if not issubclass(expected_output_type, actual_output_type):
                raise TypeError(
                    f"""
                        For function {fn}:
                        Expected output type was {expected_output_type} but got {actual_output_type}.
                        Note that you need to declare your function with a return class type!
                    """
                )
        except Exception as e:
            raise Exception(f"Could not type check output: {e}")

    @staticmethod
    def __verify_type__(element: Element):
        try:
            if not issubclass(type(element), Element):
                raise TypeError("Input element not of type Element")
        except Exception as e:
            raise Exception(f"Could not verify type of element: {e}")

class Transformer(Changeable):
    """
    A Transformer "changes the structure, not the data".
    It's function takes element.input as input and returns
    to element.output. 
    """

    def do(self, element: Element, meta: Meta = None) -> Element:
        self.__verify_type__(element=element)
        #try:
        element.output = self.fn(element.input, element.output, meta)
        # except TypeError:
        #     raise TypeError(f"A Transformer func requires args {list(fn_inp.keys())}, got func {self.fn} with {list(signature(self.fn).parameters)} kwargs")
        self.__verify_fn_output__(fn=self.fn, output=element.output)

        return element

    def __verify_fn__(self, fn: Callable[[Any, Any, Any], Any]):
        sig = signature(fn)
        args = list(sig.parameters)
        if not len(args) == 3:
            raise TypeError(f"A Transformer function must take exactly three arguments: input, output and meta. Got {args} for function {fn}")

class Mutable(Changeable):
    """
    A Mutable changes the data of the element, not the structure.
    Its function takes the element as input and freely changes
    the data of element.input or element.output. We verify after
    change that the same data type/structure is kept.
    """

    def do(self, element: Element, meta: Meta = None) -> Element:

        input_element = copy.deepcopy(element)
        self.__verify_type__(element=input_element)

        output_element = self.fn(element, meta)
        self.__verify_type__(element=output_element)
        self.__verify_fn_output__(fn=self.fn, output=output_element)

        error_msg = "A mutable can change the data and not the data type: "

        # Checks that following is true 
        #   (before)e.input == (after)e.input
        #   (before)e.output == (after)e.output

        type_input_element_input = type(input_element.input)
        type_output_element_input = type(output_element.input)
        if type_input_element_input != type_output_element_input:
            raise TypeError(error_msg + f"Gave {type_input_element_input}, got {type_output_element_input}.")

        type_input_element_output = type(input_element.output)
        type_output_element_output = type(output_element.output)
        if type_input_element_output != type_output_element_output:
            raise TypeError(error_msg + f"Gave {type_input_element_output}, got {type_output_element_output}.")


        return element

    def __verify_fn__(self, fn: Callable[[Element, Meta], Element]):
        sig = signature(fn)
        args = list(sig.parameters)
        if not len(args) == 2:
            raise TypeError(f"A Mutable function must take exactly two arguments: Element and Meta. Got {args} for function {fn}")

class VerifierRaisedException(Exception):
    pass

class Verifier(Event):
    """
    Verifier is a type of Event, taking a Changeable as input
    and runs a verifier function on the output element.
    """
    def __init__(self, changeable: Changeable, verifier_fn: Callable[[Any], Any]):
        self.chanegable = changeable
        self.verifier_fn = verifier_fn

    def do(self, element: Element, meta: Meta = None) -> Element:
        element = self.chanegable.do(
            element=element,
            meta=meta,
        )
        try:
            self.verifier_fn(element, meta)
        except VerifierRaisedException as vre:
            element.notices.add(
                Notice(
                    msg=f"Verifier did raise error: {vre}",
                    level=Level.ERROR,
                )
            )

        return element

class Chain(Event):
    """
    A Chain is a chain of events executed in a certain order and structure.
    """
    def __init__(self, ordered_events: List[Event], tag: str = None, id: str = None):
        self.ordered_events = ordered_events
        self.tag = tag
        self.id = id

    def do(self, element: Element, meta: Meta = None) -> Element:
        """
            Do chaining of given element. Meta data is optional.
            
            Args: (Element) element, (Meta) meta = None
            Return: Element
        """

        for event in self.ordered_events:
            element = self.__do_event__(event, element, meta)

        return element

    @staticmethod
    def __do_event__(event: Event, element: Element, meta: Meta = None) -> Element:
        return event.do(element, meta)

class AnyChain(Chain):
    """
    An AnyChain is a Chain, where any event must occur.
    When any event did occur, return is made.
    If no event has occured, error is thrown.
    """
    def do(self, element: Element, meta: Meta = None) -> Element:
        exceptions = []
        for event in self.ordered_events:
            try:
                element = self.__do_event__(event, element, meta)
                return element
            except Exception as e:
                exceptions.append(e)
                continue

        n_exceptions = len(exceptions)
        for i, e in zip(range(n_exceptions), exceptions):
            element.notices.add(
                Notice(
                    msg=f"Error when computing AnyChain ({i}): {e}",
                    level=Level.ERROR,
                )
            )

        return element

class AllChain(Chain):
    """
    An AllChain is a Chain, where all events has to occur, or error is thrown.
    """
    def do(self, element: Element, meta: Meta = None) -> Element:
        return super().do(element=element, meta=meta)

class ChainNotFoundException(Exception):
    pass

class Selector(Event):
    """
    A Selector takes a list of Chains as input. When run, the selector
    takes an Element and selects correct Chain to compute for that element.
    """
    def __init__(self, chains: List[Chain], logger = None, id: str = None):
        self.id = id
        self.chains = {}
        self.logger = logger
        for chain in chains:
            if chain.tag in self.chains and logger is not None:
                logger.warning(
                    f"""
                    Selector has one-to-one relation to Chain tags.
                    Chain with tag '{chain.tag}' was already registered
                    and will now be replaced.
                    """
                )
            self.chains[chain.tag] = chain

    def select(self, element: Element) -> Chain:

        """
            From all Chains, this function selects the
            correct one. There are four cases that can occur:
                (element.tag is None,     default chain is     None) -> Error  
                (element.tag is None,     default chain is not None) -> None Chain is returned
                (element.tag is not None, default chain is     None) -> Tag Chain is returned if exists, else Error
                (element.tag is not None, default chain is not None) -> None Chain is returned if not Tag Chain exists 
        """

        default_chain = self.chains.get(None, None)
        if element.tag is None and default_chain is None:
            raise ChainNotFoundException(f"Deafult (None) Chain was not registered.")
        
        elif element.tag is None and default_chain is not None:
            chain = default_chain

        elif element.tag is not None and default_chain is None:
            chain = self.chains.get(element.tag, None)
            if chain is None:
                raise ChainNotFoundException(f"Chain with tag '{element.tag}' was not registered.")
        elif element.tag is not None and default_chain is not None:
            chain = self.chains.get(element.tag, None)
            chain = default_chain if chain is None else chain

        return chain

    def do(self, element:Element, meta: Meta) -> Element:

        try:
            chain = self.select(
                element=element,
            )
            try:
                element = chain.do(
                    element=element,
                    meta=meta,
                )
            except Exception as e:
                element.notices.add(
                    Notice(
                        msg=f"Chain {type(chain)} id:{chain.id} raised '{e}'",
                        level=Level.ERROR,
                    )
                )

        except ChainNotFoundException as cnfe:
            element.notices.add(
                Notice(
                    msg=f"{cnfe}",
                    level=Level.ERROR,
                )
            )
        except Exception:
            pass

        return element

class Result(object):
    """
    After a transformation process is done, a Result is returned.
    """
    def __init__(self):
        self.elements = []
        self.notices = set()

    def elements_with(self, notice_levels: List[Level]):
        """
            Get elements that has at least one of the given notice levels.
            
            Args: (List[Level]) notice_levels
            Return: List[Element]
        """
        return [e for e in self.elements if e.has_any(levels=notice_levels)]

    def inputs(self, filter: Callable = lambda _: True):
        """
            Get input of elements. Add filter function to
            filter inputs.
            
            Args: (Callable[[Element.input], bool]) filter
            Return: List[Element.input]
        """
        return [e.input for e in self.elements if filter(e.input)]

    def outputs(self, filter: Callable = lambda _: True):
        """
            Get output of elements. Add filter function to
            filter outputs.
            
            Args: (Callable[[Element.output], bool]) filter
            Return: List[Element.output]
        """
        return [e.output for e in self.elements if filter(e.output)]

    def filter(self, fn: Callable[[Element], bool]) -> List[Element]:
        """
            Get elements with filtering function.
            
            Args: (Callable[[Element], bool]) fn
            Return: List[Element]
        """
        return [e for e in self.elements if fn(e)]

    @staticmethod
    def empty():
        return Result()

    @staticmethod
    def concatenate(*results):

        """
            Concatenates results into one result.

            Args: results *[Result]
            Return: Result
        """

        result = Result.empty()
        for _result in results:
            if not isinstance(_result, Result):
                raise Exception(f"Arguments must be of type 'Result', got: {type(_result)}")

            result.elements += _result.elements
            result.notices.update(_result.notices)

        return result

class Process(object):
    """
    A Process runs elements over Chains, linked by Selectors and other Processes, such that
    transformation is done.
    """
    def __init__(self, selector: Selector, notice_level: Level = Level.ERROR, meta: Meta = None, id: str = None, logger = None):
        self.id = id
        self.selector = selector
        self.sub_process = []
        self.notice_level = notice_level
        self.meta = meta
        self.logger = logger

    def append_subprocess(self, process):
        self.sub_process.append(process)
        return self

    @staticmethod
    def _sub_run(process, elements: List[Element]) -> Result:
        
        result = Result.empty()
        try:
            result.elements = [
                process.selector.do(
                    element=element,
                    meta=process.meta,
                )
                for element in elements
            ]
        except Exception as e:
            result.notices.add(
                Notice(
                    msg=f"Could not run process {process}:{process.id} because of error: {e}",
                    level=Level.ERROR,
                )
            )
        return result

    @staticmethod
    def _run(process, elements: List[Element]):
        result = Process._sub_run(
            process=process, 
            elements=elements,
        )
        for sub_process in process.sub_process:
            result = Process._sub_run(
                process=sub_process, 
                elements=result.elements,
            )

        return result

    def run(self, elements: List[Element]) -> Result:
        return Process._run(
            process=self,
            elements=elements,
        )

    async def run_async(self, elements: List[Element], timeout: int = 600) -> Result:
        
        try:
            distributed_elements = distribute(elements, cpu_count())
            with Pool(len(distributed_elements)) as p:
                result = p.map_async(
                    partial(Process._run, self), 
                    distributed_elements,
                ).get(timeout=timeout)

            return Result.concatenate(*result)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Process could not finish because of error: {e}")
            
            raise e