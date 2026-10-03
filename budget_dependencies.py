"""Grafo dirigido explícito, topología y cierre de dependientes, sin Qt."""
from collections import deque
from budget_values import BudgetError


class DependencyGraph:
    def __init__(self, dependencies):
        self.dependencies = {name: frozenset(refs) for name, refs in dependencies.items()}
        self.dependents = {name: set() for name in dependencies}
        for name, refs in self.dependencies.items():
            missing = refs - self.dependencies.keys()
            if missing:
                raise BudgetError('Global ' + name + ': referencias inexistentes: ' + ', '.join(sorted(missing)))
            for ref in refs:
                self.dependents[ref].add(name)
        pending = {name: len(refs) for name, refs in self.dependencies.items()}
        ready = deque(name for name, count in pending.items() if count == 0)
        order = []
        while ready:
            name = ready.popleft()
            order.append(name)
            for child in sorted(self.dependents[name]):
                pending[child] -= 1
                if not pending[child]: ready.append(child)
        if len(order) != len(pending):
            # Follow unresolved edges iteratively until finding a repeated node.
            # Avoid recursion even with very long dependency chains.
            unresolved = {name for name, count in pending.items() if count}
            name = next(name for name in pending if name in unresolved)
            path, positions = [], {}
            while name not in positions:
                positions[name] = len(path)
                path.append(name)
                name = next(ref for ref in sorted(self.dependencies[name]) if ref in unresolved)
            cycle = path[positions[name]:] + [name]
            raise BudgetError('Referencia circular entre Globals: ' + ' → '.join(cycle))
        self.order = tuple(order)
        self.dependents = {name: frozenset(refs) for name, refs in self.dependents.items()}

    def affected(self, names):
        affected = set(names) & self.dependencies.keys()
        queue = deque(affected)
        while queue:
            for child in self.dependents[queue.popleft()]:
                if child not in affected:
                    affected.add(child)
                    queue.append(child)
        return frozenset(affected)
