# MoodleMD

<h2 align="center">An open source project for creating Moodle questions and question databases entirely in Markdown, as well as for backing up existing Moodle question databases to a Markdown file.</h2>


MoodleMD is a Python script that can convert a Moodle Question Database XML file to Markdown and back. The goals of the project are:

   - To offer the convenience of editing a plain text Markdown document to create Moodle questions, instead of using the Moodle interface to create those. The Moodle web-based interface is great but can be a hurdle when maintaining and creating questions.
   - To offer support for all question types supported by Moodle out-of-the-box (without using additional plug-ins).
   - To extract all images from an XML back-up of a question database, save them as separate files, and then import those in the generated Markdown file. All of that is done automatically. Image file name clashes produce warnings. Take careful note of those.
   - To offer support for private and shared variables in all calculated type questions.
   - To offer the ability to create questions directly from Python. This can be achieved by using the Python functions already present in the script.

The goal of the project is **not** to support every single option that the Moodle web interface offers in creating new questions. For example, question feedback is not supported by the script, but can easily be added by extending the existing Python functions. 


## 1. Requirements

The following Python modules are imported by the script:

```
argparse, base64, bs4, collections, decimal, html
markdown, natsort, numpy, os, PIL, re, shutil, six
time, urllib, xml, xmltodict
```


## 2. Running the script

The included [./Example/example.md](./Example/example.md) covers all question types. One can use it as a template in creating their own questions. 

One can see the rendered output on the [Moodle MD example page](https://runningonphysics.org/MoodleMD/).

To convert the Markdown file to an XML file that can be imported directly to Moodle, issue the following command:

```
cd Example/
# Creates example.xml. If it exists, use -rw to overwrite. Use -h for help.
python ../MoodleMD.py  example.md -o example.xml
```

One can convert the XML file (or any XML back-up of an existing Moodle question database) back to Markdown. 

```
python ../MoodleMD.py  example.xml -o example_v1.md 
```

If you start with an MD file and have converted that to XML, you may want to convert the XML back to MD as a sanity check. This way you can make sure the script has done its job in parsing all questions correctly:

```
# Any differences should be unimportant:
diff example_v1.md example.md 
```

One can convert the Markdown file to html with Pandoc by using the following command. Including `table.css` is entirely optional.

```
pandoc -t html --standalone --css=./css/table.css example.md -o example.html
```

### 2.1 Usage notes

- Latex is inputted inline by enclosing in single dollar signs. 
- Once your question database has been converted to Markdown, you can play around feeding the examples to one of the AI platforms out there and asking them to generate questions on particular topics following that format.

### 2.2 Starting with a pre-existing question bank?

Export your questions to XML from Moodle, then convert the XML to markdown using the script as shown above. Please watch out for any warnings. 

To get the questions in Markdown sorted in the same order as the questions in your quizzes, you would have to rename your questions such that alphabetically sorting them results in the same order as in your quizzes. For example you may want to precede the name of question 5 in quiz 3 with something like "Qz3Q5: ...". 

## 3. Issues?

The Moodle web interface is not perfect and sometimes creates questions that do not work as intended. The MoodleMD script is also not perfect. So, if there are any crashes, you may need to dig around to figure out which question is giving you headaches. Then either delete that from the XML file or from Moodle before doing the XML back-up. If you think the question is valid and the issue is with MoodleMD, then please file a bug report including an XML file that includes the offending question.


##  4. Copyright and licensing information

 Copyright (C) 2023 Svetlin Tassev
 
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 
 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.
 
 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <https://www.gnu.org/licenses/>.



