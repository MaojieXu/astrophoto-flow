# Agent Note: Freeze archived notes

Status: implemented

## Problem

An archived note still cost a reader's attention and could still drift from the
code. Nothing on the page said it had been superseded.

## Decision

An archived note is frozen. Filing the three files under `archived/` adds an
`Archived:` line, and a sealed content hash makes later edits fail the gate.

## Alternatives considered

**Delete the note outright.** Rejected: the record still explains why an
approach was dropped.

## Consequences

An archived note is readable and is not authoritative.
