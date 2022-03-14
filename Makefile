# Standard Makefile for compiling LaTeX documents in the Supertech
# group.

DOC=tc
APPENDIX=tc_appendix
#$(shell basename $(CURDIR))

# This line is intentionally blank.

#TARGETS=$(patsubst %,%.pdf,$(DOC))

OTHERS = Makefile pldi2018.bib # plain-url.bst supertech.sty allpapers.bib

DEPS_DIR = .deps

INCLUDE_DIR=.

LATEXMK = TEXINPUTS=$(INCLUDE_DIR)/: BIBINPUTS=$(INCLUDE_DIR)/: BSTINPUTS=$(INCLUDE_DIR)/: latexmk -f
LATEXMK_FLAGS = -pdflatex="pdflatex --shell-escape %O %S" -pdf -dvi- -ps- -recorder -M -MP \
                  -e 'show_cus_dep();'

all: $(DOC).pdf $(APPENDIX).pdf

-include $(DEPS_DIR)/$(DOC).pdfP

ifneq (,$(findstring B,$(MAKEFLAGS)))
LATEXMK_FLAGS += -gg
endif

$(DEPS_DIR) :
	if [ ! -d $(DEPS_DIR) ]; then mkdir $@; fi

$(DOC).pdf : $(OTHERS)
$(APPENDIX).pdf : $(OTHERS)

###########################################################################
## Make targets for cleaning

clean:
	rm -f *.aux *.dvi *.bbl *.blg *.tmp *.lof *.log *.toc *.out *.fls *.fdb_latexmk $(DEPS_DIR)/*.pdfP $(DOC).pdf *~



###########################################################################
## Make targets for document

pdf : $(DOC).pdf $(APPENDIX).pdf

answer : taco_answer.pdf

%.pdf : %.tex $(OTHERS)
	if [ ! -e $(DEPS_DIR) ]; then mkdir $(DEPS_DIR); fi
	$(LATEXMK) $(LATEXMK_FLAGS) -MF $(DEPS_DIR)/$@P $<
	if [ -e $@ ]; then touch $@; fi

Extra/autotuner.pdf: Extra/autotuner.svg
	inkscape -z --export-pdf=$@ $<

# Some nonsense that latexmk doesn't understand with minted can be fixed by telling that these rules are easy.
%.w18 %.out.pyg %.aex: %.tex
	@echo > /dev/null
# remake :
# 	if [ ! -e $(DEPS_DIR) ]; then mkdir $(DEPS_DIR); fi
# 	$(LATEXMK) -g -deps-out=$(DEPS_DIR)/$(DOC).pdfP $(DOC).tex
# 	if [ -e $(DOC).pdf ]; then touch $(DOC).pdf; fi

all: pdf answer
