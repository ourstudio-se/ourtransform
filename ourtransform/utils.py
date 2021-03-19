import numpy as np

def distribute(items, n):

    """
        Distributes items into n (almost) equally large batches.
        Example: items = [1,2,3,4,5,6,7,8,9], n = 4 gives batches = [[1,5,9], [2,6], [3,7], [4,8]]

        Args: 
            data ([any]): List of items of any type
            n (int): Number of max items of a batch

        Returns:
            [[any]]: List of lists of items of any type
    """

    batches = [[] for _ in range(n)]
    for i in range(len(items)):
        item = items[i]
        batches[i % n].append(item)
    return [b for b in batches if not len(b) == 0]
