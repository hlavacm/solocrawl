"""Constraint-aware version resolution across ecosystems."""

from __future__ import annotations

import operator
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


class InvalidConstraintError(ValueError):
    """Raised when a version constraint cannot be parsed."""


@dataclass(frozen=True)
class VersionEntry:
    """A version string with optional yanked metadata."""

    version: str
    yanked: bool = False


VersionPredicate = Callable[[Version], bool]
ConstraintParser = Callable[[str], VersionPredicate]
VersionNormalizer = Callable[[str], str]


def _parse_pep440_constraint(constraint: str) -> VersionPredicate:
    """Parse a PEP 440 specifier set (``>=4.2,<5``) into a predicate."""
    try:
        specifiers = SpecifierSet(constraint)
    except InvalidSpecifier as exc:
        msg = f"invalid version constraint: {constraint!r}"
        raise InvalidConstraintError(msg) from exc

    def matches(version: Version) -> bool:
        return version in specifiers

    return matches


_OPERATORS: dict[str, Callable[[Version, Version], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "=": operator.eq,
    "!=": operator.ne,
}

# Matches a single semver comparator: an optional operator/caret/tilde followed by a version-ish
# token (digits, dots, wildcards, pre-release/build metadata).
_COMPARATOR_RE = re.compile(
    r"(>=|<=|>|<|==|=|!=|\^|~)?\s*([vV]?[0-9][0-9A-Za-z.\-+]*|[vV]?[0-9]*[xX*][0-9A-Za-z.\-+xX*]*|\*)"
)


def parse_semver_constraint(constraint: str) -> VersionPredicate:
    """Parse an npm/Composer-style semver range into a predicate.

    Supports ``^``/``~``, ``x``/``*`` wildcards, hyphen ranges, ``||`` (OR),
    comma/space-separated AND clauses, and the usual comparators.
    """
    alternatives = [part.strip() for part in constraint.split("||")]
    predicates = [_parse_semver_alternative(part, constraint) for part in alternatives if part]
    if not predicates:
        msg = f"invalid version constraint: {constraint!r}"
        raise InvalidConstraintError(msg)

    def matches(version: Version) -> bool:
        return any(predicate(version) for predicate in predicates)

    return matches


def _parse_semver_alternative(text: str, original: str) -> VersionPredicate:
    hyphen = re.split(r"\s+-\s+", text)
    if len(hyphen) == 2:
        lower = _version_from_parts(_numeric_parts(hyphen[0], original))
        upper = _version_from_parts(_numeric_parts(hyphen[1], original))
        return lambda version: lower <= version <= upper

    bounds: list[tuple[Callable[[Version, Version], bool], Version]] = []
    matched_any = False
    for match in _COMPARATOR_RE.finditer(text):
        matched_any = True
        bounds.extend(_comparator_bounds(match.group(1), match.group(2), original))

    if not matched_any:
        msg = f"invalid version constraint: {original!r}"
        raise InvalidConstraintError(msg)

    def matches(version: Version) -> bool:
        return all(op(version, bound) for op, bound in bounds)

    return matches


def _comparator_bounds(
    op_token: str | None,
    version_token: str,
    original: str,
) -> list[tuple[Callable[[Version, Version], bool], Version]]:
    token = version_token.strip()

    if op_token in _OPERATORS:
        return [(_OPERATORS[op_token], _version_or_error(token, original))]

    if op_token == "^":
        parts = _numeric_parts(token, original)
        lower = _version_from_parts(parts)
        return [(operator.ge, lower), (operator.lt, _caret_upper(parts))]

    if op_token == "~":
        parts = _numeric_parts(token, original)
        lower = _version_from_parts(parts)
        return [(operator.ge, lower), (operator.lt, _tilde_upper(parts))]

    # No operator: bare version, wildcard, or partial range.
    stripped = token.lstrip("vV")
    if stripped in ("", "*", "x", "X"):
        return [(operator.ge, Version("0"))]

    has_wildcard = bool(re.search(r"[xX*]", stripped))
    parts = _numeric_parts(token, original)
    if has_wildcard or len(parts) < 3:
        lower = _version_from_parts(parts)
        return [(operator.ge, lower), (operator.lt, _partial_upper(parts))]

    return [(operator.eq, _version_or_error(token, original))]


def _numeric_parts(text: str, original: str) -> list[int]:
    """Return the leading numeric ``major[.minor[.patch]]`` parts of a token."""
    core = text.strip().lstrip("vV")
    for separator in ("-", "+"):
        index = core.find(separator)
        if index != -1:
            core = core[:index]

    parts: list[int] = []
    for piece in core.split("."):
        if piece in ("x", "X", "*", ""):
            break
        if not piece.isdigit():
            msg = f"invalid version constraint: {original!r}"
            raise InvalidConstraintError(msg)
        parts.append(int(piece))

    if not parts:
        msg = f"invalid version constraint: {original!r}"
        raise InvalidConstraintError(msg)
    return parts


def _version_from_parts(parts: list[int]) -> Version:
    padded = (parts + [0, 0, 0])[:3]
    return Version(".".join(str(part) for part in padded))


def _caret_upper(parts: list[int]) -> Version:
    padded = (parts + [0, 0, 0])[:3]
    for index, value in enumerate(padded):
        if value != 0:
            bumped = padded[:index] + [padded[index] + 1] + [0] * (2 - index)
            return _version_from_parts(bumped)
    # All-zero: bump the least-significant component that was provided.
    last = min(len(parts), 3) - 1
    bumped = [0, 0, 0]
    bumped[last] = 1
    return _version_from_parts(bumped)


def _tilde_upper(parts: list[int]) -> Version:
    if len(parts) >= 2:
        return _version_from_parts([parts[0], parts[1] + 1, 0])
    return _version_from_parts([parts[0] + 1, 0, 0])


def _partial_upper(parts: list[int]) -> Version:
    if len(parts) >= 2:
        return _version_from_parts([parts[0], parts[1] + 1, 0])
    return _version_from_parts([parts[0] + 1, 0, 0])


def _version_or_error(token: str, original: str) -> Version:
    try:
        return Version(token)
    except InvalidVersion as exc:
        msg = f"invalid version constraint: {original!r}"
        raise InvalidConstraintError(msg) from exc


def _parse_version(
    version: str,
    *,
    normalizer: VersionNormalizer | None = None,
) -> Version | None:
    if normalizer is not None:
        version = normalizer(version)
    try:
        return Version(version)
    except InvalidVersion:
        return None


def resolve_latest(
    versions: Iterable[str | VersionEntry],
    *,
    constraint: str | None = None,
    allow_prerelease: bool = False,
    constraint_parser: ConstraintParser | None = None,
    version_normalizer: VersionNormalizer | None = None,
) -> str | None:
    """Return the highest version satisfying optional constraints."""
    predicate: VersionPredicate | None = None
    if constraint is not None and constraint.strip():
        parser = constraint_parser or _parse_pep440_constraint
        predicate = parser(constraint.strip())

    candidates: list[tuple[Version, str]] = []
    for item in versions:
        if isinstance(item, VersionEntry):
            if item.yanked:
                continue
            version_str = item.version
        else:
            version_str = item

        parsed = _parse_version(version_str, normalizer=version_normalizer)
        if parsed is None:
            continue
        if not allow_prerelease and parsed.is_prerelease:
            continue
        if predicate is not None and not predicate(parsed):
            continue
        candidates.append((parsed, version_str))

    if not candidates:
        return None

    return max(candidates, key=lambda item: item[0])[1]


def previous_versions(
    versions: Iterable[str | VersionEntry],
    *,
    latest: str,
    count: int = 3,
    allow_prerelease: bool = False,
    version_normalizer: VersionNormalizer | None = None,
) -> list[str]:
    """Return a few versions immediately below ``latest``."""
    parsed_latest = _parse_version(latest, normalizer=version_normalizer)
    if parsed_latest is None:
        return []

    candidates: list[tuple[Version, str]] = []
    for item in versions:
        if isinstance(item, VersionEntry):
            if item.yanked:
                continue
            version_str = item.version
        else:
            version_str = item

        parsed = _parse_version(version_str, normalizer=version_normalizer)
        if parsed is None or parsed >= parsed_latest:
            continue
        if not allow_prerelease and parsed.is_prerelease:
            continue
        candidates.append((parsed, version_str))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [version for _, version in candidates[: max(0, count)]]


def normalize_go_module_version(version: str) -> str:
    """Strip a leading ``v`` so Go module tags parse as semver."""
    if version.startswith(("v", "V")):
        return version[1:]
    return version
