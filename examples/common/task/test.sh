#!/bin/sh
# The test suite of calc.sh: `sh test.sh` exits with 0 when every test passes.
failed=0
check() {
    expected=$1
    shift
    actual=$(sh ./calc.sh "$@")
    if [ "$actual" = "$expected" ]; then
        echo "ok   calc $*"
    else
        echo "FAIL calc $*: expected $expected, got $actual"
        failed=1
    fi
}
check 5 add 2 3
check 1 sub 3 2
check 6 mul 2 3
exit $failed
