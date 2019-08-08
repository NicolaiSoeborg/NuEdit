.PHONY: run
run: 
	python -Xdev -m nuedit

.PHONY: count
count:
	(find nuedit/ -iname "*.py" -exec cat {} \;)  | egrep -v '^$$|^ *#' | wc -l
