## Old
- Ideally the html should be generated automatically on the fly and served to the browser
- Those JS libs had that kind of a framework

## Wed Jul  4 12:34:11 IST 2018
- Most of the things are working now.
- Now just need to organize the files and directories and tweak/fix the templates

### Next Todo
- Instead of directives, perhaps I can store information in yaml metadata.
- Directives should be at the top of the markdown files to indicate
  what is it to be generated from each file, so that it doesn't have
  to be specified at the command line.
- Additional directives in comments should be there so that both
  slides and html from a markdown file can be generated simultaneously
  with certain elements being included and excluded.
- The search path should also be configurable but that can be handled easily.
- Specifically tweak the latex template for:
  - Fix all the imports/includes
  - Change the bibliography manager to biber
  - Must rerun `pdflatex` multiple times to ensure references and toc are generated correctly.
  - Though I think `pandoc` should take care of generating metadata so that multiple runs of 
    `pdflatex` are not required.
  - But I should check the logs for errors and act/warn appropriately.
  - Or maybe just figure out why pandoc isn't compiling to pdf correctly.
  - Latex options have to be put in different templates so that doc generation is seamless.
    - The different types of documents can be specified from the `-V` option.
- For the beamer template:
  - Automatic section, frametitle and center block generation with hints.
- Must pretty up the html template.
- What about reveal js slides from markdown? Should I tinker with
  `pandoc` templates? Or should I include markdown in reveal?
  - For revealjs also I'll have to make a separate directory to store all the stuff like markdown and all
  - Nesting of slides for revealjs. Will have to customize the template
- html to pdf should be straightforward depending on the type of document to be generated.
