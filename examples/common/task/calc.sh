#!/bin/sh
# A tiny calculator: `sh calc.sh add|sub|mul A B` prints the result.
op=$1
a=$2
b=$3
case "$op" in
add) echo $((a + b)) ;;
sub) echo $((a + b)) ;;
mul) echo $((a * b)) ;;
*)
    echo "unknown operation: $op" >&2
    exit 2
    ;;
esac
