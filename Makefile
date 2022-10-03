.PHONY: run
run: 
	python -Xdev -m nuedit

.PHONY: typecheck
typecheck: 
	mypy nuedit/

.PHONY: count
count:
	(find nuedit/ -iname "*.py" -exec cat {} \;)  | egrep -v '^$$|^ *#' | wc -l

.PHONY: xicoretmp
xicoretmp:
	cp xi-editor/rust/target/debug/xi-core /tmp/
