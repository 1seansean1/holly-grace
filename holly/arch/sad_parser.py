"""Parser for Mermaid flowchart SAD files → structured AST.

Parses the Holly SAD mermaid format into a typed AST containing:
- Subgraphs (layers, regions)
- Nodes (components) with labels
- Edges (connections) with labels and styles
- Style class definitions and assignments
- Init/config directives
- Comments

This is a *structural* parser — it understands the mermaid flowchart grammar
enough to extract architectural information, not a full mermaid renderer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


# ── Edge style classification ────────────────────────

class EdgeStyle(Enum):
    """How the edge is drawn in mermaid."""
    SOLID = auto()        # -->  ---  ---|
    DOTTED = auto()       # -.->  -.-
    THICK = auto()        # ==>  ===


class EdgeDirection(Enum):
    """Arrow direction."""
    FORWARD = auto()      # -->
    BACKWARD = auto()     # <--
    BOTH = auto()         # <-->
    NONE = auto()         # ---


# ── AST node types ───────────────────────────────────

@dataclass
class MermaidComment:
    """A %% comment line."""
    text: str
    line_no: int


@dataclass
class MermaidInit:
    """%%{init: ...}%% directive."""
    raw: str
    line_no: int


@dataclass
class MermaidNode:
    """A component node in the flowchart."""
    node_id: str
    label: str                          # text inside the shape brackets
    shape: str = "rect"                 # rect, round, stadium, etc.
    line_no: int = 0
    parent_subgraph: str | None = None  # subgraph id this node belongs to
    style_classes: list[str] = field(default_factory=list)

    @property
    def label_lines(self) -> list[str]:
        """Split multi-line label (\\n separated) into individual lines."""
        return [line.strip() for line in self.label.split("\\n") if line.strip()]


@dataclass
class MermaidEdge:
    """A connection between two nodes."""
    source: str
    target: str
    label: str = ""
    style: EdgeStyle = EdgeStyle.SOLID
    direction: EdgeDirection = EdgeDirection.FORWARD
    line_no: int = 0


@dataclass
class MermaidSubgraph:
    """A subgraph (layer/region) container."""
    subgraph_id: str
    title: str = ""
    direction: str = ""                 # TB, LR, etc.
    line_no: int = 0
    parent_subgraph: str | None = None
    children_ids: list[str] = field(default_factory=list)  # node & subgraph ids
    style_classes: list[str] = field(default_factory=list)


@dataclass
class StyleClassDef:
    """A classDef statement."""
    class_name: str
    properties: str  # raw CSS-like property string
    line_no: int = 0


@dataclass
class StyleClassAssignment:
    """A class X,Y,Z className statement."""
    node_ids: list[str]
    class_name: str
    line_no: int = 0


# ── Full AST ─────────────────────────────────────────

@dataclass
class MermaidAST:
    """Complete parsed AST of a mermaid flowchart."""
    chart_type: str = "flowchart"       # flowchart, graph
    chart_direction: str = "TB"         # TB, LR, etc.
    init_directives: list[MermaidInit] = field(default_factory=list)
    comments: list[MermaidComment] = field(default_factory=list)
    nodes: dict[str, MermaidNode] = field(default_factory=dict)
    edges: list[MermaidEdge] = field(default_factory=list)
    subgraphs: dict[str, MermaidSubgraph] = field(default_factory=dict)
    style_defs: dict[str, StyleClassDef] = field(default_factory=dict)
    style_assignments: list[StyleClassAssignment] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def subgraph_count(self) -> int:
        return len(self.subgraphs)

    def nodes_in_subgraph(self, subgraph_id: str) -> list[MermaidNode]:
        """Return all nodes directly inside a subgraph."""
        return [n for n in self.nodes.values() if n.parent_subgraph == subgraph_id]

    def subgraphs_in_subgraph(self, subgraph_id: str) -> list[MermaidSubgraph]:
        """Return all child subgraphs of a given subgraph."""
        return [s for s in self.subgraphs.values() if s.parent_subgraph == subgraph_id]

    def style_classes_for_node(self, node_id: str) -> list[str]:
        """Return all style classes assigned to a node."""
        classes: list[str] = []
        for assignment in self.style_assignments:
            if node_id in assignment.node_ids:
                classes.append(assignment.class_name)
        return classes


# ── Regex patterns ───────────────────────────────────

# Init directive: %%{init: {...}}%%
_RE_INIT = re.compile(r"^%%\{.*\}%%$")

# Comment: %% text
_RE_COMMENT = re.compile(r"^\s*%%\s?(.*)")

# Chart declaration: flowchart TB | graph LR
_RE_CHART = re.compile(r"^\s*(flowchart|graph)\s+(TB|BT|LR|RL|TD)\s*$")

# Subgraph start: subgraph ID["Title"]  or  subgraph ID
_RE_SUBGRAPH = re.compile(
    r'^\s*subgraph\s+(\w+)(?:\[(["\'])(.+?)\2\])?\s*$'
)

# Direction inside subgraph: direction TB
_RE_DIRECTION = re.compile(r"^\s*direction\s+(TB|BT|LR|RL|TD)\s*$")

# End of subgraph
_RE_END = re.compile(r"^\s*end\s*$")

# Node shape patterns  (id["label"], id("label"), id(["label"]), etc.)
# Ordered longest-open first to avoid greedy mismatches.
_NODE_SHAPES: list[tuple[str, str, str]] = [
    # Quoted variants (standard Holly SAD format)
    (r'\(\["', r'"\]\)', "stadium"),   # (["label"])
    (r'\[\("', r'"\)\]', "cylinder"),  # [("label")]
    (r'\{\{"', r'"\}\}', "hexagon"),   # {{"label"}}
    (r'\["', r'"\]', "rect"),          # ["label"]
    (r'\("', r'"\)', "round"),         # ("label")
    # Unquoted variants (broader Mermaid compat)
    (r'\(\[', r'\]\)', "stadium"),     # ([label])
    (r'\[\(', r'\)\]', "cylinder"),    # [(label)]
    (r'\{\{', r'\}\}', "hexagon"),     # {{label}}
    (r'\[', r'\]', "rect"),            # [label]
    (r'\(', r'\)', "round"),           # (label)
    (r'\{', r'\}', "rhombus"),         # {label}
]

# Edge patterns — order matters (longest match first)
_EDGE_PATTERNS: list[tuple[str, EdgeStyle, EdgeDirection]] = [
    (r"<==>", EdgeStyle.THICK, EdgeDirection.BOTH),
    (r"==>", EdgeStyle.THICK, EdgeDirection.FORWARD),
    (r"<==", EdgeStyle.THICK, EdgeDirection.BACKWARD),
    (r"===", EdgeStyle.THICK, EdgeDirection.NONE),
    (r"<-.->", EdgeStyle.DOTTED, EdgeDirection.BOTH),
    (r"-.->", EdgeStyle.DOTTED, EdgeDirection.FORWARD),
    (r"<-.-", EdgeStyle.DOTTED, EdgeDirection.BACKWARD),
    (r"-\.-", EdgeStyle.DOTTED, EdgeDirection.NONE),
    (r"<-->", EdgeStyle.SOLID, EdgeDirection.BOTH),
    (r"-->", EdgeStyle.SOLID, EdgeDirection.FORWARD),
    (r"<--", EdgeStyle.SOLID, EdgeDirection.BACKWARD),
    (r"---", EdgeStyle.SOLID, EdgeDirection.NONE),
]

# classDef name props
_RE_CLASSDEF = re.compile(r"^\s*classDef\s+(\w+)\s+(.+)$")

# class N1,N2,N3 className
_RE_CLASSASSIGN = re.compile(r"^\s*class\s+([\w,\s]+)\s+(\w+)\s*$")


# ── Parser ───────────────────────────────────────────

def _extract_node_and_label(token: str) -> tuple[str, str, str] | None:
    """Try to parse 'ID[\"label\"]' or similar shape syntax.

    Returns (node_id, label, shape) or None.
    """
    for open_pat, close_pat, shape in _NODE_SHAPES:
        m = re.match(rf'^(\w+){open_pat}(.*?){close_pat}$', token, re.DOTALL)
        if m:
            return m.group(1), m.group(2), shape
    # Bare ID (no brackets)
    m = re.match(r"^(\w+)$", token)
    if m:
        return m.group(1), m.group(1), "bare"
    return None


def _parse_edge_line(line: str, line_no: int) -> tuple[list[MermaidNode], list[MermaidEdge]]:
    """Parse a line containing node definitions and/or edges.

    Handles: A --> B, A -->|"label"| B, A["Label"] --> B["Label"],
    A --- B, A -.-> B, chained edges A --> B --> C, etc.

    Strategy: use finditer to locate edge operators and labels,
    then extract node tokens from the gaps.
    """
    nodes: list[MermaidNode] = []
    edges: list[MermaidEdge] = []

    stripped = line.strip()

    # Sort edge patterns longest-first for correct matching
    edge_ops = sorted(_EDGE_PATTERNS, key=lambda x: -len(x[0]))

    # Build a single regex that matches: optional_pre_label edge_op optional_post_label
    # Label format: |"text"|, |'text'|, or |text| (unquoted)
    op_alts = "|".join(re.escape(pat) for pat, _, _ in edge_ops)
    # Match: |"quoted"|, |'quoted'|, or |unquoted| (no pipe chars inside)
    label_pat = r'(?:\|"([^"]*?)"\||\|' + r"'([^']*?)'" + r'\||\|([^|]*?)\|)'
    edge_re = re.compile(
        rf'\s*{label_pat}?\s*({op_alts})\s*{label_pat}?\s*'
    )

    # Find all edge operators in the line
    edge_matches = list(edge_re.finditer(stripped))

    if not edge_matches:
        # No edges — might be a standalone node definition like: K1["Schema\nValidation"]
        result = _extract_node_and_label(stripped)
        if result:
            node_id, label, shape = result
            nodes.append(MermaidNode(
                node_id=node_id, label=label, shape=shape, line_no=line_no,
            ))
        return nodes, edges

    # Extract node tokens from gaps between edge operators
    node_tokens: list[str] = []
    prev_end = 0
    edge_infos: list[tuple[EdgeStyle, EdgeDirection, str]] = []

    for match in edge_matches:
        # Node token before this edge operator
        before = stripped[prev_end:match.start()].strip()
        if before:
            node_tokens.append(before)

        # Determine edge style/direction
        # Groups: 1=pre-dquote, 2=pre-squote, 3=pre-unquoted, 4=edge_op,
        #         5=post-dquote, 6=post-squote, 7=post-unquoted
        op_str = match.group(4)
        style = EdgeStyle.SOLID
        direction = EdgeDirection.FORWARD
        for pat, s, d in edge_ops:
            if op_str == pat:
                style = s
                direction = d
                break

        # Edge label (from pre-label or post-label, any quoting style)
        label = (
            match.group(1) or match.group(2) or match.group(3)
            or match.group(5) or match.group(6) or match.group(7)
            or ""
        )
        edge_infos.append((style, direction, label))

        prev_end = match.end()

    # Node token after the last edge operator
    after = stripped[prev_end:].strip()
    if after:
        node_tokens.append(after)

    # Parse each node token
    parsed_nodes: list[tuple[str, str, str]] = []
    for token in node_tokens:
        result = _extract_node_and_label(token)
        if result:
            parsed_nodes.append(result)
            node_id, label, shape = result
            nodes.append(MermaidNode(
                node_id=node_id, label=label, shape=shape, line_no=line_no,
            ))

    # Build edges between consecutive node pairs
    for idx, (style, direction, label) in enumerate(edge_infos):
        if idx < len(parsed_nodes) - 1:
            source_id = parsed_nodes[idx][0]
            target_id = parsed_nodes[idx + 1][0]
            edges.append(MermaidEdge(
                source=source_id,
                target=target_id,
                label=label,
                style=style,
                direction=direction,
                line_no=line_no,
            ))

    return nodes, edges


def parse_sad(source: str, *, source_path: str = "<string>") -> MermaidAST:
    """Parse a mermaid flowchart string into a MermaidAST.

    Args:
        source: The full mermaid source text.
        source_path: Optional path for error messages.

    Returns:
        Populated MermaidAST.
    """
    ast = MermaidAST()
    lines = source.splitlines()

    subgraph_stack: list[str] = []  # stack of subgraph IDs (for nesting)

    for line_no_0, raw_line in enumerate(lines):
        line_no = line_no_0 + 1  # 1-indexed
        stripped = raw_line.strip()

        if not stripped:
            continue

        # Init directive
        if _RE_INIT.match(stripped):
            ast.init_directives.append(MermaidInit(raw=stripped, line_no=line_no))
            continue

        # Comment (but not init)
        cm = _RE_COMMENT.match(stripped)
        if cm:
            ast.comments.append(MermaidComment(text=cm.group(1), line_no=line_no))
            continue

        # Chart type declaration
        chart_m = _RE_CHART.match(stripped)
        if chart_m:
            ast.chart_type = chart_m.group(1)
            ast.chart_direction = chart_m.group(2)
            continue

        # Subgraph start
        sg_m = _RE_SUBGRAPH.match(stripped)
        if sg_m:
            sg_id = sg_m.group(1)
            sg_title = sg_m.group(3) or sg_id
            parent = subgraph_stack[-1] if subgraph_stack else None
            sg = MermaidSubgraph(
                subgraph_id=sg_id,
                title=sg_title,
                line_no=line_no,
                parent_subgraph=parent,
            )
            ast.subgraphs[sg_id] = sg
            if parent and parent in ast.subgraphs:
                ast.subgraphs[parent].children_ids.append(sg_id)
            subgraph_stack.append(sg_id)
            continue

        # Direction inside subgraph
        dir_m = _RE_DIRECTION.match(stripped)
        if dir_m and subgraph_stack:
            ast.subgraphs[subgraph_stack[-1]].direction = dir_m.group(1)
            continue

        # End subgraph
        if _RE_END.match(stripped):
            if subgraph_stack:
                subgraph_stack.pop()
            continue

        # classDef
        cd_m = _RE_CLASSDEF.match(stripped)
        if cd_m:
            ast.style_defs[cd_m.group(1)] = StyleClassDef(
                class_name=cd_m.group(1),
                properties=cd_m.group(2),
                line_no=line_no,
            )
            continue

        # class assignment
        ca_m = _RE_CLASSASSIGN.match(stripped)
        if ca_m:
            node_ids = [nid.strip() for nid in ca_m.group(1).split(",")]
            class_name = ca_m.group(2)
            assignment = StyleClassAssignment(
                node_ids=node_ids,
                class_name=class_name,
                line_no=line_no,
            )
            ast.style_assignments.append(assignment)
            # Also set on individual nodes if they exist
            for nid in node_ids:
                if nid in ast.nodes:
                    ast.nodes[nid].style_classes.append(class_name)
            continue

        # Node definitions and edges (the bulk of the work)
        # Check if line contains any edge operator or node definition
        has_edge_op = any(
            re.search(re.escape(pat), stripped)
            for pat, _, _ in _EDGE_PATTERNS
        )
        has_node_def = bool(re.search(r'\w+[\[\(\{]', stripped))

        if has_edge_op or has_node_def:
            new_nodes, new_edges = _parse_edge_line(stripped, line_no)
            current_sg = subgraph_stack[-1] if subgraph_stack else None
            for node in new_nodes:
                existing = ast.nodes.get(node.node_id)
                if existing is None:
                    node.parent_subgraph = current_sg
                    ast.nodes[node.node_id] = node
                    if current_sg and current_sg in ast.subgraphs:
                        ast.subgraphs[current_sg].children_ids.append(node.node_id)
                elif existing.shape == "bare" and node.shape != "bare":
                    # Upgrade: a richer definition replaces a bare reference
                    node.parent_subgraph = existing.parent_subgraph or current_sg
                    node.style_classes = existing.style_classes
                    ast.nodes[node.node_id] = node
            for edge in new_edges:
                ast.edges.append(edge)

    # Post-pass: apply style class assignments to nodes that were defined after
    for assignment in ast.style_assignments:
        for nid in assignment.node_ids:
            if nid in ast.nodes and assignment.class_name not in ast.nodes[nid].style_classes:
                ast.nodes[nid].style_classes.append(assignment.class_name)

    return ast


def parse_sad_file(path: Path) -> MermaidAST:
    """Parse a mermaid SAD file from disk."""
    source = path.read_text(encoding="utf-8")
    return parse_sad(source, source_path=str(path))
