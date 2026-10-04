"""Constraint-aware version resolution using PEP 440 or SemVer ordering."""

from __future__ import annotations

import operator
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cmp_to_key

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from semver import Version as SemVersion


class InvalidConstraintError(ValueError):
    """Raised when a version constraint cannot be parsed completely."""


@dataclass(frozen=True)
class VersionEntry:
    """A version string with optional yanked metadata."""

    version: str
    yanked: bool = False


ParsedVersion = Version | SemVersion
VersionPredicate = Callable[[ParsedVersion], bool]
ConstraintParser = Callable[[str], VersionPredicate]
VersionNormalizer = Callable[[str], str]
Bound = tuple[Callable[[int, int], bool], SemVersion]
_OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "=": operator.eq,
    "!=": operator.ne,
}
_TOKEN = r"[vV]?(?:\d+|[xX*])(?:\.(?:\d+|[xX*])){0,2}(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
_COMPARATOR_RE = re.compile(r"(>=|<=|==|!=|>|<|=|\^|~)?\s*(" + _TOKEN + r")")
_VERSION_RE = re.compile(r"[vV]?(\d+(?:\.\d+){0,2})([-+].*)?")


def _invalid(constraint: str) -> InvalidConstraintError:
    return InvalidConstraintError(f"invalid version constraint: {constraint!r}")


def _parse_pep440_constraint(constraint: str) -> VersionPredicate:
    try:
        specifiers = SpecifierSet(constraint)
    except InvalidSpecifier as exc:
        raise _invalid(constraint) from exc
    return lambda version: (
        isinstance(version, Version)
        and specifiers.contains(
            version,
            prereleases=True,
        )
    )


def _semver(text: str) -> SemVersion:
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        raise ValueError("invalid semantic version")
    parts = match[1].split(".")
    return SemVersion.parse(".".join(parts + ["0"] * (3 - len(parts))) + (match[2] or ""))


def parse_semver_constraint(constraint: str) -> VersionPredicate:
    """Parse common caret, tilde, wildcard, hyphen, AND and OR SemVer ranges.

    The entire input must match this grammar. Ecosystem-specific range syntax
    outside this common subset is rejected rather than interpreted partially.
    """
    alternatives = [part.strip() for part in constraint.split("||")]
    if not all(alternatives):
        raise _invalid(constraint)
    try:
        predicates = [_parse_semver_alternative(part) for part in alternatives]
    except ValueError as exc:
        raise _invalid(constraint) from exc

    def matches(version: ParsedVersion) -> bool:
        if isinstance(version, Version):
            # Native numeric registries can have four release components. Keep their
            # existing packaging ordering while applying the common range bounds.
            try:
                return any(
                    all(op(_compare(version, _numeric_bound(bound)), 0) for op, bound in bounds)
                    for bounds in predicates
                )
            except InvalidVersion as exc:
                raise _invalid(constraint) from exc
        candidate = version
        return any(
            all(op(candidate.compare(bound), 0) for op, bound in bounds) for bounds in predicates
        )

    return matches


def _numeric_bound(bound: SemVersion) -> Version:
    if bound.prerelease == "0":
        return Version(f"{bound.major}.{bound.minor}.{bound.patch}.dev0")
    return Version(str(bound))


def _parse_semver_alternative(text: str) -> list[Bound]:
    hyphen = re.fullmatch(r"(" + _TOKEN + r")\s+-\s+(" + _TOKEN + r")", text)
    if hyphen:
        lower, upper = _semver(hyphen[1]), _semver(hyphen[2])
        parts = _numeric_parts(hyphen[2])
        if len(parts) < 3:
            return [(operator.ge, lower), (operator.lt, _partial_upper(parts))]
        return [(operator.ge, lower), (operator.le, upper)]

    bounds: list[Bound] = []
    position = 0
    while position < len(text):
        match = _COMPARATOR_RE.match(text, position)
        if match is None:
            raise ValueError("unrecognized comparator")
        bounds.extend(_comparator_bounds(match[1], match[2]))
        position = match.end()
        if position == len(text):
            break
        separator = re.match(r"(?:\s*,\s*|\s+)", text[position:])
        if separator is None:
            raise ValueError("missing separator")
        position += separator.end()
        if position == len(text):
            raise ValueError("missing comparator")
    return bounds


def _numeric_parts(token: str) -> list[int]:
    core = re.split(r"[-+]", token.lstrip("vV"), maxsplit=1)[0]
    pieces = core.split(".")
    parts: list[int] = []
    wildcard = False
    for piece in pieces:
        if piece in {"x", "X", "*"}:
            wildcard = True
        elif wildcard or not piece.isdigit():
            raise ValueError("invalid wildcard")
        else:
            if len(piece) > 1 and piece.startswith("0"):
                raise ValueError("leading zero")
            parts.append(int(piece))
    return parts


def _version_from_parts(parts: list[int]) -> SemVersion:
    return SemVersion(*(parts + [0] * (3 - len(parts))))


def _partial_upper(parts: list[int]) -> SemVersion:
    bumped = parts[:-1] + [parts[-1] + 1]
    return _version_from_parts(bumped).replace(prerelease="0")


def _comparator_bounds(op: str | None, token: str) -> list[Bound]:
    parts = _numeric_parts(token)
    wildcard = bool(re.search(r"[xX*]", re.split(r"[-+]", token, maxsplit=1)[0]))
    if not parts:
        if op not in {None, "=", "=="} or "-" in token or "+" in token:
            raise ValueError("invalid wildcard comparator")
        return []
    if wildcard:
        if op not in {None, "=", "=="} or "-" in token or "+" in token:
            raise ValueError("invalid wildcard comparator")
        return [(operator.ge, _version_from_parts(parts)), (operator.lt, _partial_upper(parts))]
    lower = _semver(token)
    if op in _OPERATORS:
        if len(parts) < 3 and lower.prerelease is None and lower.build is None:
            if op == ">":
                return [(operator.ge, _partial_upper(parts).replace(prerelease=None))]
            if op == "<=":
                return [(operator.lt, _partial_upper(parts))]
            if op == "<":
                return [(operator.lt, lower.replace(prerelease="0"))]
            if op in {"=", "=="}:
                return [(operator.ge, lower), (operator.lt, _partial_upper(parts))]
            if op == "!=":
                raise ValueError("partial exclusion comparator is unsupported")
        return [(_OPERATORS[op], lower)]
    if op == "^":
        # For zero-major partials, only the components actually specified pin the range.
        index = next((i for i, part in enumerate(parts) if part), len(parts) - 1)
        upper = _version_from_parts(parts[:index] + [parts[index] + 1]).replace(prerelease="0")
        return [(operator.ge, lower), (operator.lt, upper)]
    if op == "~":
        return [(operator.ge, lower), (operator.lt, _partial_upper(parts[:2]))]
    if len(parts) < 3 and lower.prerelease is None and lower.build is None:
        return [(operator.ge, lower), (operator.lt, _partial_upper(parts))]
    return [(operator.eq, lower)]


def _parse_version(
    version: str, *, normalizer: VersionNormalizer | None = None, semver: bool = False
) -> ParsedVersion | None:
    if normalizer is not None:
        version = normalizer(version)
    try:
        return _semver(version) if semver else Version(version)
    except InvalidVersion, ValueError:
        return None


def _compare(left: ParsedVersion, right: ParsedVersion) -> int:
    if isinstance(left, SemVersion) and isinstance(right, SemVersion):
        return left.compare(right)
    if isinstance(left, Version) and isinstance(right, Version):
        return (left > right) - (left < right)
    raise TypeError("cannot compare version schemes")


def _is_prerelease(version: ParsedVersion) -> bool:
    return bool(version.prerelease) if isinstance(version, SemVersion) else version.is_prerelease


def resolve_latest(
    versions: Iterable[str | VersionEntry],
    *,
    constraint: str | None = None,
    allow_prerelease: bool = False,
    constraint_parser: ConstraintParser | None = None,
    version_normalizer: VersionNormalizer | None = None,
    semver: bool | None = None,
) -> str | None:
    """Return the highest eligible version; SemVer parsers select SemVer ordering."""
    predicate = None
    if constraint is not None:
        parser = constraint_parser or _parse_pep440_constraint
        predicate = parser(constraint.strip())
    use_semver = constraint_parser is parse_semver_constraint if semver is None else semver
    candidates: list[tuple[ParsedVersion, str]] = []
    for item in versions:
        if isinstance(item, VersionEntry) and item.yanked:
            continue
        text = item.version if isinstance(item, VersionEntry) else item
        parsed = _parse_version(text, normalizer=version_normalizer, semver=use_semver)
        if parsed is None or (not allow_prerelease and _is_prerelease(parsed)):
            continue
        if predicate is None or predicate(parsed):
            candidates.append((parsed, text))
    if not candidates:
        return None
    return max(candidates, key=cmp_to_key(lambda a, b: _compare(a[0], b[0])))[1]


def previous_versions(
    versions: Iterable[str | VersionEntry],
    *,
    latest: str,
    count: int = 3,
    allow_prerelease: bool = False,
    version_normalizer: VersionNormalizer | None = None,
    semver: bool = False,
) -> list[str]:
    """Return eligible versions immediately below ``latest`` using the same scheme."""
    parsed_latest = _parse_version(latest, normalizer=version_normalizer, semver=semver)
    if parsed_latest is None:
        return []
    candidates: list[tuple[ParsedVersion, str]] = []
    for item in versions:
        if isinstance(item, VersionEntry) and item.yanked:
            continue
        text = item.version if isinstance(item, VersionEntry) else item
        parsed = _parse_version(text, normalizer=version_normalizer, semver=semver)
        if parsed is None or _compare(parsed, parsed_latest) >= 0:
            continue
        if not allow_prerelease and _is_prerelease(parsed):
            continue
        candidates.append((parsed, text))
    candidates.sort(key=cmp_to_key(lambda a, b: _compare(a[0], b[0])), reverse=True)
    return [text for _, text in candidates[: max(0, count)]]


def normalize_go_module_version(version: str) -> str:
    """Strip a leading ``v`` so Go module tags parse as SemVer."""
    return version[1:] if version.startswith(("v", "V")) else version
