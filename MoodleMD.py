#!/usr/bin/env python
# coding: utf-8

# # Markdownify

# In[12]:


from bs4 import BeautifulSoup, NavigableString, Comment, Doctype
import re
import six


convert_heading_re = re.compile(r'convert_h(\d+)')
line_beginning_re = re.compile(r'^', re.MULTILINE)
whitespace_re = re.compile(r'[\t ]+')
all_whitespace_re = re.compile(r'[\s]+')
html_heading_re = re.compile(r'h[1-6]')


# Heading styles
ATX = 'atx'
ATX_CLOSED = 'atx_closed'
UNDERLINED = 'underlined'
SETEXT = UNDERLINED

# Newline style
SPACES = 'spaces'
BACKSLASH = 'backslash'

# Strong and emphasis style
ASTERISK = '*'
UNDERSCORE = '_'


def escape(text):
    if not text:
        return ''
    return text.replace('_', r'\_')


def chomp(text):
    """
    If the text in an inline tag like b, a, or em contains a leading or trailing
    space, strip the string and return a space as suffix of prefix, if needed.
    This function is used to prevent conversions like
        <b> foo</b> => ** foo**
    """
    prefix = ' ' if text and text[0] == ' ' else ''
    suffix = ' ' if text and text[-1] == ' ' else ''
    text = text.strip()
    return (prefix, suffix, text)


def abstract_inline_conversion(markup_fn):
    """
    This abstracts all simple inline tags like b, em, del, ...
    Returns a function that wraps the chomped text in a pair of the string
    that is returned by markup_fn. markup_fn is necessary to allow for
    references to self.strong_em_symbol etc.
    """
    def implementation(self, el, text, convert_as_inline):
        markup = markup_fn(self)
        prefix, suffix, text = chomp(text)
        if not text:
            return ''
        return '%s%s%s%s%s' % (prefix, markup, text, markup, suffix)
    return implementation

def abstract_inline_conversion2(markup_fn):
    """
    This abstracts all simple inline tags like b, em, del, ...
    Returns a function that wraps the chomped text in a pair of the string
    that is returned by markup_fn. markup_fn is necessary to allow for
    references to self.strong_em_symbol etc.
    """
    def implementation(self, el, text, convert_as_inline):
        markup = markup_fn(self)
        prefix, suffix, text = chomp(text)
        if not text:
            return ''
        return '%s%s%s%s%s' % (prefix, markup[0], text, markup[1], suffix)
    return implementation

def _todict(obj):
    return dict((k, getattr(obj, k)) for k in dir(obj) if not k.startswith('_'))


class MarkdownConverter(object):
    class DefaultOptions:
        autolinks = True
        bullets = '*+-'  # An iterable of bullet types.
        convert = None
        default_title = False
        heading_style = UNDERLINED
        newline_style = SPACES
        strip = None
        strong_em_symbol = ASTERISK
        sub_symbol = ''
        sup_symbol = ''

    class Options(DefaultOptions):
        pass

    def __init__(self, **options):
        # Create an options dictionary. Use DefaultOptions as a base so that
        # it doesn't have to be extended.
        self.options = _todict(self.DefaultOptions)
        self.options.update(_todict(self.Options))
        self.options.update(options)
        if self.options['strip'] is not None and self.options['convert'] is not None:
            raise ValueError('You may specify either tags to strip or tags to'
                             ' convert, but not both.')

    def convert(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        return self.process_tag(soup, convert_as_inline=False, children_only=True)

    def process_tag(self, node, convert_as_inline, children_only=False):
        text = ''
        # markdown headings can't include block elements (elements w/newlines)
        isHeading = html_heading_re.match(node.name) is not None
        convert_children_as_inline = convert_as_inline

        if not children_only and isHeading:
            convert_children_as_inline = True

        # Remove whitespace-only textnodes in purely nested nodes
        def is_nested_node(el):
            return el and el.name in ['ol', 'ul', 'li',
                                      'table', 'thead', 'tbody', 'tfoot',
                                      'tr', 'td', 'th']

        if is_nested_node(node):
            for el in node.children:
                # Only extract (remove) whitespace-only text node if any of the
                # conditions is true:
                # - el is the first element in its parent
                # - el is the last element in its parent
                # - el is adjacent to an nested node
                can_extract = (not el.previous_sibling
                               or not el.next_sibling
                               or is_nested_node(el.previous_sibling)
                               or is_nested_node(el.next_sibling))
                if (isinstance(el, NavigableString)
                        and six.text_type(el).strip() == ''
                        and can_extract):
                    el.extract()

        # Convert the children first
        for el in node.children:
            if isinstance(el, Comment) or isinstance(el, Doctype):
                continue
            elif isinstance(el, NavigableString):
                text += self.process_text(el)
            else:
                text += self.process_tag(el, convert_children_as_inline)

        if not children_only:
            convert_fn = getattr(self, 'convert_%s' % node.name, None)
            if convert_fn and self.should_convert_tag(node.name):
                text = convert_fn(node, text, convert_as_inline)

        return text

    def process_text(self, el):
        text = six.text_type(el) or ''

        # dont remove any whitespace when handling pre or code in pre
        if not (el.parent.name == 'pre'
                or (el.parent.name == 'code'
                    and el.parent.parent.name == 'pre')):
            text = whitespace_re.sub(' ', text)

        if el.parent.name != 'code':
            text = escape(text)

        # remove trailing whitespaces if any of the following condition is true:
        # - current text node is the last node in li
        # - current text node is followed by an embedded list
        if (el.parent.name == 'li'
                and (not el.next_sibling
                     or el.next_sibling.name in ['ul', 'ol'])):
            text = text.rstrip()

        return text

    def __getattr__(self, attr):
        # Handle headings
        m = convert_heading_re.match(attr)
        if m:
            n = int(m.group(1))

            def convert_tag(el, text, convert_as_inline):
                return self.convert_hn(n, el, text, convert_as_inline)

            convert_tag.__name__ = 'convert_h%s' % n
            setattr(self, convert_tag.__name__, convert_tag)
            return convert_tag

        raise AttributeError(attr)

    def should_convert_tag(self, tag):
        tag = tag.lower()
        strip = self.options['strip']
        convert = self.options['convert']
        if strip is not None:
            return tag not in strip
        elif convert is not None:
            return tag in convert
        else:
            return True

    def indent(self, text, level):
        return line_beginning_re.sub('\t' * level, text) if text else ''

    def underline(self, text, pad_char):
        text = (text or '').rstrip()
        return '%s\n%s\n\n' % (text, pad_char * len(text)) if text else ''

    def convert_a(self, el, text, convert_as_inline):
        prefix, suffix, text = chomp(text)
        if not text:
            return ''
        if convert_as_inline:
            return text
        href = el.get('href')
        title = el.get('title')
        # For the replacement see #29: text nodes underscores are escaped
        if (self.options['autolinks']
                and text.replace(r'\_', '_') == href
                and not title
                and not self.options['default_title']):
            # Shortcut syntax
            return '<%s>' % href
        if self.options['default_title'] and not title:
            title = href
        title_part = ' "%s"' % title.replace('"', r'\"') if title else ''
        return '%s[%s](%s%s)%s' % (prefix, text, href, title_part, suffix) if href else text

    convert_b = abstract_inline_conversion(lambda self: 2 * self.options['strong_em_symbol'])

    def convert_blockquote(self, el, text, convert_as_inline):

        if convert_as_inline:
            return text

        return '\n' + (line_beginning_re.sub('> ', text) + '\n\n') if text else ''

    def convert_br(self, el, text, convert_as_inline):
        t=False
        for p in el.parents:
            if p.name in ['td']:
                t=True
        if t:
            return '<br>'
        else:
            return '\n\n'


    def convert_code(self, el, text, convert_as_inline):
        if el.parent.name == 'pre':
            return text
        converter = abstract_inline_conversion(lambda self: '`')
        return converter(self, el, text, convert_as_inline)

    convert_del = abstract_inline_conversion(lambda self: '~~')
    
    #convert_tbody = abstract_inline_conversion(lambda self: '')

    convert_em = abstract_inline_conversion(lambda self: self.options['strong_em_symbol'])

    convert_kbd = convert_code

    def convert_hn(self, n, el, text, convert_as_inline):
        if convert_as_inline:
            return text

        style = self.options['heading_style'].lower()
        text = text.rstrip()
        if style == UNDERLINED and n <= 2:
            line = '=' if n == 1 else '-'
            return self.underline(text, line)
        hashes = '#' * n
        if style == ATX_CLOSED:
            return '%s %s %s\n\n' % (hashes, text, hashes)
        return '%s %s\n\n' % (hashes, text)

    def convert_hr(self, el, text, convert_as_inline):
        if not(el.parent.name in ['tbody','tr','td','table']):
            return '\n\n---\n\n'
        else:
            return '<hr>'
  
    convert_i = convert_em

    def convert_img(self, el, text, convert_as_inline):
        alt = el.attrs.get('alt', None) or ''
        src = el.attrs.get('src', None) or ''
        title = el.attrs.get('title', None) or ''
        title_part = ' "%s"' % title.replace('"', r'\"') if title else ''
        if convert_as_inline:
            return alt

        return '![%s](%s%s)' % (alt, src, title_part)

    def convert_list(self, el, text, convert_as_inline):

        # Converting a list to inline is undefined.
        # Ignoring convert_to_inline for list.

        nested = False
        before_paragraph = False
        if el.next_sibling and el.next_sibling.name not in ['ul', 'ol']:
            before_paragraph = True
        while el:
            if el.name == 'li':
                nested = True
                break
            el = el.parent
        if nested:
            # remove trailing newline if nested
            return '\n' + self.indent(text, 1).rstrip()
        return text + ('\n' if before_paragraph else '')

    convert_ul = convert_list
    convert_ol = convert_list

    def convert_li(self, el, text, convert_as_inline):
        parent = el.parent
        if parent is not None and parent.name == 'ol':
            if parent.get("start"):
                start = int(parent.get("start"))
            else:
                start = 1
            bullet = '%s.' % (start + parent.index(el))
        else:
            depth = -1
            while el:
                if el.name == 'ul':
                    depth += 1
                el = el.parent
            bullets = self.options['bullets']
            bullet = bullets[depth % len(bullets)]
        return '%s %s\n' % (bullet, text or '')

    def convert_span(self, el, text, convert_as_inline):
        return ' %s ' % text if text else ''
    
    def convert_p(self, el, text, convert_as_inline):
        t=False
        for p in el.parents:
            #if p.name in ['tbody','tr','td','table']:
            if p.name in ['td']:
                t=True
        if t:
            return '%s<br>' % text if text else ''
        else:
            return '%s\n\n' % text if text else ''

    
    def convert_pre(self, el, text, convert_as_inline):
        if not text:
            return ''
        return '\n```\n%s\n```\n' % text

    convert_s = convert_del

    convert_strong = convert_b

    convert_samp = convert_code

    convert_sub = abstract_inline_conversion2(lambda self: ["<sub>","</sub>"])

    convert_sup = abstract_inline_conversion2(lambda self: ["<sup>","</sup>"])

    def convert_table(self, el, text, convert_as_inline):
        return '\n\n' + text + '\n'

    def convert_td(self, el, text, convert_as_inline):
        return ' ' + text.replace("\n"," ") + ' |'

    def convert_th(self, el, text, convert_as_inline):
        return ' ' + text.replace("\n"," ") + ' |'

    def convert_tr(self, el, text, convert_as_inline):
        cells = el.find_all(['td', 'th'])
        is_headrow = all([cell.name == 'th' for cell in cells])
        #print(is_headrow)
        #is_headrow = (
        #    all([cell.name == 'th' for cell in cells])
        #    or (not el.previous_sibling and not el.parent.name == 'tbody')
        #    or (not el.previous_sibling and el.parent.name == 'tbody' and len(el.parent.parent.find_all(['thead'])) < 1)
        #)
        overline = ''
        underline = ''
        if is_headrow and (not(el.previous_sibling) or el.parent.previous_sibling.name=='tbody'):
            # first row and is headline: print headline underline
            underline += '| ' + ' | '.join(['---'] * len(cells)) + ' |' + '\n'
        elif not el.previous_sibling and (len(el.parent.parent.find_all(['thead'])) < 1):
            # first row, not headline, and the parent is sth. like tbody:
            # print empty headline above this row
            overline += '| ' + ' | '.join([''] * len(cells)) + ' |' + '\n'
            overline += '| ' + ' | '.join(['---'] * len(cells)) + ' |' + '\n'
        return overline + '|' + text + '\n' + underline


def markdownify(html, **options):
    html=html.replace(r"_",r"UNDERSCORECHAR")
    text= MarkdownConverter(**options).convert(html)
    return text.replace("UNDERSCORECHAR",r"_")


# In[13]:


from markdown.extensions.tables import TableExtension
import markdown
from collections.abc import Iterable

def flatten(xs):
    for x in xs:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            yield from flatten(x)
        else:
            yield x

def flatten_list(x):
    return [i for i in flatten(x)]

def markdownToHTML(text):
    text_split=text.split("$")
    math_list=text_split.copy()[1::2]
    for i in range(len(text_split)):
        if (i%2==1):
            text_split[i]="PLACEHOLDERFORSOMEMATHHERE"
    text="".join(text_split)
    text_split=text.split(r"![](")
    for j in range(len(text_split)):
        if (j>0):
            k=0
            while (text_split[j][k]!=")"):
                k+=1
            if k<len(text_split[j])-1:
                if text_split[j][k+1]=="{":
                    while (text_split[j][k]!="}"):
                        k+=1
            text_split[j]=[text_split[j][:k],text_split[j][k+1:]]
    ts=flatten_list(text_split)
    image_list=ts.copy()[1::2]
    for i in range(len(ts)):
        if (i%2==1):
            ts[i]="PLACEHOLDERFORSOMEIMAGEHERE"
    text="".join(ts)
    #text_split=text.split(r"**")
    #text=""
    #for i in range(len(text_split)-1):
    #   text+=text_split[i]
    #   if (i%2==0):
    #       text+=r"<strong>"
    #   else:
    #       text+=r"</strong>"
    #text+=text_split[-1]
    text=text.replace(r"_",r"UNDERSCORECHAR")
    text=markdown.markdown(text,extensions=['tables'])
    text=text.replace(r"UNDERSCORECHAR",r"_")
    text_split=text.split("PLACEHOLDERFORSOMEMATHHERE")
    text=""
    for i in range(len(text_split)-1):
        text+=text_split[i]+"$"+math_list[i]+"$"
    text+=text_split[-1]
    text_split=text.split("PLACEHOLDERFORSOMEIMAGEHERE")
    text=""
    for i in range(len(text_split)-1):
        if "{width=" in image_list[i]:
            text+=text_split[i]+r"![]("+image_list[i]+r"}"
        else:
            text+=text_split[i]+r"![]("+image_list[i]+r")"
    text+=text_split[-1]
    return text


# # Arguments of functions to XML

# In[14]:


import os


# In[15]:


import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element as Ele
from xml.etree.ElementTree import SubElement as Sub
DEFAULT_TOL=0.0125


# In[16]:


def fix_latex(s):
    s=s.split("$")
    i=1
    t=""
    for p in s:
        if (i%2==0):
            #p=p.replace("{","{ ")
            p=r"\("+p+r"\)"
        t+=p
        i+=1
    t=t.replace("\n\n","</p><p>")
    t=t.replace(r"DOLLAR_SIGN",r"$")
    return t


# In[17]:


import base64
def import_image(questiontext,filename,serverfilename="",width=550):
    filename=filename.replace("$","SsS").replace(r"?","QqQ")
    if (serverfilename==""):
        serverfilename=filename
    with open(filename, "rb") as imageFile:
        encodedString = base64.b64encode(imageFile.read())
    f=Sub(questiontext,'file')
    f.set('name',serverfilename)
    f.set('path',r"/")
    f.set('encoding',"base64")
    f.text=encodedString.decode("ASCII")
    #print(encodedString)
    if width!=0:
        return (r"""<img src="@@PLUGINFILE@@/"""+serverfilename+r"""" alt="" role="presentation" class="img-fluid atto_image_button_text-bottom" """+"width=\""
                +
                str(width)+r"""">""")
    else:
        return (r"""<img src="@@PLUGINFILE@@/"""+serverfilename+r"""" alt="" role="presentation" class="img-fluid atto_image_button_text-bottom" """+r"""">""")


# In[18]:


import re
def extract_arg_of_function(text,f,brackets=["(",")"]):
    indices_object = re.finditer(pattern=f, string=text)
    LEFT = [index.end() for index in indices_object]
    #LEFT = [l+len(brackets[0])-1 for l in LEFT]
    res = list()
    left = list()
    for i in range(len(text)):
        if text[i:i+len(brackets[0])] ==brackets[0]:
            left.append(i)
        if text[i:i+len(brackets[1])] ==brackets[1]:
            try:
                le = left.pop()
                if le in LEFT:
                    arg=res.append(text[le + len(brackets[0]):i])
            except:
                left=[]
    return res


def extract_arg_of_function2(text,f,brackets=["(",")"]):
    indices_object = re.finditer(pattern=f, string=text)
    LEFT = [index.end() for index in indices_object]
    #print(LEFT)
    #LEFT = [l+len(brackets[0])-1 for l in LEFT]
    res = list()
    left = list()
    #print(LEFT)
    i=0
    while (i<len(text)):
        if (i<=len(text)-len(brackets[0])) and (text[i:i+len(brackets[0])] == brackets[0]):
            if i in LEFT:
                left.append(i)
                i+=len(brackets[0])
        if (i<=len(text)-len(brackets[1])):
            if text[i:i+len(brackets[1])] == brackets[1]:
                try:
                    le = left.pop()
                    if le in LEFT:
                        arg=res.append(text[le + len(brackets[0]):i])
                except:
                    left=[]
        i+=1
    return res


# In[ ]:





# In[19]:


def fix_images(t,text):
    IMG_filenames=text.split(r"![](")
    for j in range(len(IMG_filenames)):
        if (j>0):
            k=0
            while (IMG_filenames[j][k]!=")"):
                k+=1
            if k<len(IMG_filenames[j])-1:
                if IMG_filenames[j][k+1]=="{":
                    while (IMG_filenames[j][k]!="}"):
                        k+=1
            IMG_filenames[j]=IMG_filenames[j][:k]
    IMG_filenames.pop(0)
    for img in IMG_filenames:
        img1=img.split(r"){width=")
        if (len(img1)==1):
            width=0
            img_name=img1[0]
            end=')'
        else:
            width=int(img1[1])
            img_name=img1[0]
            end='}'
        img_import_text=import_image(t,img_name,width=width)
        
        text=text.replace(r"![]("+img+end,img_import_text)
    return text


# In[20]:


import numpy as np

def round_to_sigfigs(num, sigfigs=3):
    if (type(num)==np.ndarray) or (type(num)==list):
        if (type(sigfigs)==np.ndarray) or (type(sigfigs)==list):
            v=[]
            for i in range(num.len()):
                x=num[i]
                v.append(round(x, (sigfigs[i]-int(np.floor(np.log10(np.abs(x))))-1)))
            return np.array(v)
        else:
            v=[]
            for x in num:
                v.append(round(x, (sigfigs-int(np.floor(np.log10(np.abs(x))))-1)))
            return np.array(v)
    else:
        return round(num, (sigfigs-int(np.floor(np.log10(np.abs(num))))-1))
                     
def floor_to_sigfigs(num,sigfigs=3):
    if (np.abs(num)<1.e-100):
        return 0.0
    else:
        c =10**(-1+sigfigs-np.floor(np.log10(np.abs(num))))
        c1=10**(1-sigfigs+np.floor(np.log10(np.abs(num))))
        
        return round_to_sigfigs(np.floor(num*c)*c1,sigfigs)

def ceil_to_sigfigs(num,sigfigs=3):
    if (np.abs(num)<1.e-100):
        return 0.0
    else:
        c =10**(-1+sigfigs-np.floor(np.log10(np.abs(num))))
        c1=10**(1-sigfigs+np.floor(np.log10(np.abs(num))))
        return round_to_sigfigs(np.ceil(num*c)*c1,sigfigs)


def sample_var(name,minmax=[1,10],count=50,shared=True,decimals=-1e6,sigfigs=3):
    vals=np.random.uniform(minmax[0],minmax[1],size=count)
    if (decimals==-1e6):
        decimals=-(1+np.floor(np.log10(max(np.abs(minmax[0]),np.abs(minmax[1]))))-sigfigs)
    vals=round_to_sigfigs(vals,sigfigs)
    if (decimals<=-0):
        decimals=0
    return {"name":name,
            "minmax":minmax,
            "decimals":round(decimals),
            "values":vals,
            "shared":shared,'order':0}

def create_var_from_array(name,arr,shared=True,sigfigs=3,extrema_sigfigs=1,order=0,expression=''):
    arr=round_to_sigfigs(arr,sigfigs)
    min_arr=np.min(arr)
    max_arr=np.max(arr)
    min_arr=floor_to_sigfigs(min_arr,extrema_sigfigs)
    max_arr=ceil_to_sigfigs(max_arr,extrema_sigfigs)
    minmax=[min_arr,max_arr]
    decimals=-(1+np.floor(np.log10(max(np.abs(minmax[0]),np.abs(minmax[1]))))-sigfigs)
    if (decimals<=-0):
        decimals=0
    return {"name":name,
            "minmax":minmax,
            "decimals":round(decimals),
            "values":arr,
            "shared":shared,
            'order':order,
            'expression':expression
           }


# In[21]:


def create_category(quiz,name):
    q=Sub(quiz,'question')
    q.set('type','category')
    Sub(Sub(q,'category'),'text').text="$course$/"+name


# In[22]:


def create_shortanswer(quiz,name,text,answers,case="0"):
    q=Sub(quiz,'question')
    q.set('type','shortanswer')
    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    Sub(q,'usecase').text=case
    Sub(q,'penalty').text="0.3333333"
    Sub(q,'hidden').text="0"
    v=0
    for i in answers:
        v=max(v,i[1])
    if (v!=100.0):
        raise Exception('One of your answers should weigh 100%')
    ####
    for ans in answers:
        a=Sub(q,'answer')
        a.set('fraction',str(ans[1]))
        a.set('format','moodle_auto_format')
        Sub(a,'text').text=ans[0]


# In[23]:


def create_ddimageortext(quiz,name,text,dragdrop,shuffle=True):
    q=Sub(quiz,'question')
    q.set('type','ddimageortext')
    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    if shuffle:
        Sub(q,'shuffleanswers').text="1"
    else:
        Sub(q,'shuffleanswers').text="0"
    Idrop=1
    Idrag=0
    
    end=False
    
    for dd in dragdrop.split("\n"):
        dd=dd.strip()
        try:
            if dd[:4]=='![](':
                import_image(q,dd[4:].split(")")[0],width=0)
        except:
            None
        if len(dd) > 4:
            if (dd[0]=='|') and (dd[1]!=":") and (dd[1:].strip()[:4]!="Drop"):
                a=dd.split('|')
                a.pop(0)
                #print(a)
                if a[2].strip()!='':
                    use=0
                    Idrag+=1
                    drag=Sub(q,'drag')
                    Sub(drag,'no').text=str(Idrag)
                    Sub(drag,'draggroup').text=a[1].strip()
                    if "![](" in a[2]:
                        fn=a[2].split('![](')[1].split(")")[0]
                        import_image(drag,fn,width=0)
                    else:
                        Sub(drag,'text').text=fix_latex(a[2].strip())
                    if a[3].strip() in ['YES','Yes','yes','y','Y','inf','Inf','INF','INFINITY','Infinity','infinity']:
                        Sub(drag,'infinite')
                if a[0].strip()!='':
                    #print('drop')
                    use+=1
                    #print(drag.findall('./infinite'))
                    #print(a[2])
                    if (len(drag.findall('./infinite'))==0) and (use>1):
                        raise Exception('Using a drag item more times than set in table.')
                    drop=Sub(q,'drop')
                    xy=a[0].split(',')
                    Sub(drop,'no').text=str(Idrop)
                    Sub(drop,'xleft').text=xy[0].strip()
                    Sub(drop,'ytop').text=xy[1].strip()
                    Sub(drop,'choice').text=str(Idrag)
                    #print('ok')
                    Idrop+=1
                end=True
            elif (end):
                return


# In[24]:


def create_ddmarker(quiz,name,text,dragdrop,shuffle=True,showmisplaced=True):
    q=Sub(quiz,'question')
    if showmisplaced:
        Sub(q,'showmisplaced')
    q.set('type','ddmarker')
    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    if shuffle:
        Sub(q,'shuffleanswers').text="1"
    else:
        Sub(q,'shuffleanswers').text="0"
    Idrop=1
    Idrag=0
    end=False
    for dd in dragdrop.split("\n"):
        dd=dd.strip()
        try:
            if dd[:4]=='![](':
                import_image(q,dd[4:].split(")")[0],width=0)
        except:
            None
        if len(dd) > 4:
            if (dd[0]=='|') and (dd[1]!=":") and (dd[1:].strip()[:4]!="Drop"):
                a=dd.split('|')
                a.pop(0)
                if a[2].strip()!='':
                    use=0
                    Idrag+=1
                    drag=Sub(q,'drag')
                    Sub(drag,'no').text=str(Idrag)
                    Sub(drag,'text').text=fix_latex(a[2].strip())
                    if a[3].strip() in ['YES','Yes','yes','y','Y','inf','Inf','INF','INFINITY','infinity','Infinity']:
                        Sub(drag,'infinite')
                    else:
                        try:
                            nn=int(a[3].strip())
                        except:
                            nn=1
                        Sub(drag,'noofdrags').text=str(nn)
                if a[0].strip()!='':
                    use+=1
                    if len(drag.findall('./infinite'))==0:
                        if use>nn:
                            raise Exception('Using a drag item more times than set in table.')
                    drop=Sub(q,'drop')
                    Sub(drop,'no').text=str(Idrop)
                    Sub(drop,'shape').text=a[0].strip()
                    Sub(drop,'coords').text=a[1].strip()
                    Sub(drop,'choice').text=str(Idrag)
                    Idrop+=1
                end=True
            elif (end):
                return
                    


# In[25]:


def create_description(quiz,name,text):
    q=Sub(quiz,'question')
    q.set('type','description')
    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    Sub(q,'defaultgrade').text="0.0000"
    Sub(q,'penalty').text="0.0000"
    Sub(q,'hidden').text="0"
    
def create_essay(quiz,name,text):
    q=Sub(quiz,'question')
    q.set('type','essay')
    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text


# In[ ]:


def create_randomsamatch(quiz,name,text,choose,subcats):
    q=Sub(quiz,'question')
    q.set('type','randomsamatch')
    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    if subcats:
        Sub(q,'subcats').text='1'
    Sub(q,'choose').text=str(choose)


# In[26]:


def create_matching(quiz,name,text,QA,shuffle=True):
    q=Sub(quiz,'question')
    q.set('type','matching')
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    if shuffle:
        Sub(q,'shuffleanswers').text="true"
    else:
        Sub(q,'shuffleanswers').text="false"
    Sub(Sub(q,'name'),'text').text=name
    
    for qa in QA:
        n=Sub(q,'subquestion')
        Sub(n,'text').text=r"<![CDATA["+fix_latex(qa[0].strip())+r"]]>"
        Sub(Sub(n,'answer'),'text').text=r"<![CDATA["+fix_latex(qa[1].strip())+r"]]>"


# In[ ]:


def create_calculatedmulti(quiz,name,text,answers,var,tolerance=DEFAULT_TOL,tolerancetype="1",correctanswerformat="2",correctanswerlength=3,single_answer=True):
    q=Sub(quiz,'question')
    q.set('type','calculatedmulti')

    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    ####
    Sub(q,'defaultgrade').text="1.0"
    Sub(q,'penalty').text="0.3333333"
    Sub(q,'hidden').text="0"
    Sub(q,'synchronize').text="1"
    if single_answer:
        Sub(q,'single').text="1"
    else:
        Sub(q,'single').text="0"
        
    
    v=0
    if single_answer:
        for i in answers:
            v=max(v,i[1])
        if (v!=100.0):
            raise Exception('One of your single answers should weigh 100%')
    else:
        for i in answers:
            v+=max(0,i[1])
        if (v<99.99):
            raise Exception('The weights of the answers should add up to 100%')
        
        
    Sub(q,'answernumbering').text="abc"
    Sub(q,'shuffleanswers').text="1"
    Sub(q,'unitgradingtype').text="0"
    Sub(q,'unitpenalty').text="0.1000000"
    Sub(q,'showunits').text="3"
    Sub(q,'unitsleft').text="0"
    ####
    if type(answers)==str:
        answers=[[answers,100]]
    for ans in answers:
        a=Sub(q,'answer')
        a.set('fraction',str(ans[1]))
        Sub(a,'text').text=ans[0]
        if len(ans)==3:
            tolerance=abs(ans[2])
        if len(ans)==4:
            correctanswerlength=ans[3]
        Sub(a,'tolerance').text=str(tolerance)
        Sub(a,'tolerancetype').text=tolerancetype  #1=relative (set default) 2=nominal
        Sub(a,'correctanswerformat').text=correctanswerformat # 2=sigfigs (set default) 1=decimals
        Sub(a,'correctanswerlength').text=str(correctanswerlength)
    ####
    data=Sub(q,"dataset_definitions")
    for v in var:
        data1=Sub(data,"dataset_definition")
        try:
            if len(v['expression'])>0:
                Sub(Sub(data1,'expression'),"text").text=r"<![CDATA["+v['expression']+"]]>"
                Sub(data1,'order').text=str(v['order'])
        except:
            None
        #print(v['name']+"   "+str(v["shared"]))
        if v["shared"]==True:
            Sub(Sub(data1,"status"),"text").text="shared"
        else:
            Sub(Sub(data1,"status"),"text").text="private"
        Sub(Sub(data1,"name"),"text").text=v['name']
        Sub(data1,"type").text='calculated'
        Sub(Sub(data1,"distribution"),"text").text="uniform"
        Sub(Sub(data1,"minimum"),"text").text=str(v["minmax"][0])
        Sub(Sub(data1,"maximum"),"text").text=str(v["minmax"][1])
        Sub(Sub(data1,"decimals"),"text").text=str(v["decimals"])
        Sub(data1,"itemcount").text=str(len(v["values"]))
        Sub(data1,"number_of_items").text=str(len(v["values"]))
        items=Sub(data1,'dataset_items')
        i=1
        for val in v["values"]:
            item=Sub(items,'dataset_item')
            Sub(item,'number').text=str(i)
            Sub(item,'value').text=str(val)
            i+=1


# In[27]:


def create_calculated(quiz,name,text,answers,var,tolerance=DEFAULT_TOL,tolerancetype="1",correctanswerformat="2",correctanswerlength=3):
    q=Sub(quiz,'question')
    q.set('type','calculated')

    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    ####
    Sub(q,'defaultgrade').text="1.0"
    Sub(q,'penalty').text="0.3333333"
    Sub(q,'hidden').text="0"
    Sub(q,'synchronize').text="1"
    Sub(q,'single').text="0"
    Sub(q,'answernumbering').text="abc"
    Sub(q,'shuffleanswers').text="1"
    Sub(q,'unitgradingtype').text="0"
    Sub(q,'unitpenalty').text="0.1000000"
    Sub(q,'showunits').text="3"
    Sub(q,'unitsleft').text="0"
    ####
    if type(answers)==str:
        answers=[[answers,100]]
    for ans in answers:
        a=Sub(q,'answer')
        a.set('fraction',str(ans[1]))
        Sub(a,'text').text=ans[0]
        if len(ans)==3:
            tolerance=abs(ans[2])
        if len(ans)==4:
            correctanswerlength=ans[3]
        Sub(a,'tolerance').text=str(tolerance)
        Sub(a,'tolerancetype').text=tolerancetype  #1=relative (set default) 2=nominal
        Sub(a,'correctanswerformat').text=correctanswerformat # 2=sigfigs (set default) 1=decimals
        Sub(a,'correctanswerlength').text=str(correctanswerlength)
    ####
    data=Sub(q,"dataset_definitions")
    for v in var:
        data1=Sub(data,"dataset_definition")
        try:
            if len(v['expression'])>0:
                Sub(Sub(data1,'expression'),"text").text=r"<![CDATA["+v['expression']+"]]>"
                Sub(data1,'order').text=str(v['order'])
        except:
            None
        #print(v['name']+"   "+str(v["shared"]))
        if v["shared"]==True:
            Sub(Sub(data1,"status"),"text").text="shared"
        else:
            Sub(Sub(data1,"status"),"text").text="private"
        Sub(Sub(data1,"name"),"text").text=v['name']
        Sub(data1,"type").text='calculated'
        Sub(Sub(data1,"distribution"),"text").text="uniform"
        Sub(Sub(data1,"minimum"),"text").text=str(v["minmax"][0])
        Sub(Sub(data1,"maximum"),"text").text=str(v["minmax"][1])
        Sub(Sub(data1,"decimals"),"text").text=str(v["decimals"])
        Sub(data1,"itemcount").text=str(len(v["values"]))
        Sub(data1,"number_of_items").text=str(len(v["values"]))
        items=Sub(data1,'dataset_items')
        i=1
        for val in v["values"]:
            item=Sub(items,'dataset_item')
            Sub(item,'number').text=str(i)
            Sub(item,'value').text=str(val)
            i+=1


# In[28]:


def create_calculated_simple(quiz,name,text,answers,var,tolerance=DEFAULT_TOL,tolerancetype="1",correctanswerformat="2",correctanswerlength=3):
    q=Sub(quiz,'question')
    q.set('type','calculatedsimple')

    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    ####
    Sub(q,'defaultgrade').text="1.0"
    Sub(q,'penalty').text="0.3333333"
    Sub(q,'hidden').text="0"
    Sub(q,'synchronize').text="0"
    Sub(q,'single').text="0"
    Sub(q,'answernumbering').text="abc"
    Sub(q,'shuffleanswers').text="0"
    Sub(q,'unitgradingtype').text="0"
    Sub(q,'unitpenalty').text="0.1000000"
    Sub(q,'showunits').text="3"
    Sub(q,'unitsleft').text="0"
    ####
    if type(answers)==str:
        answers=[[answers,100]]
    for ans in answers:
        a=Sub(q,'answer')
        a.set('fraction',str(ans[1]))
        Sub(a,'text').text=ans[0]
        if len(ans)==3:
            tolerance=abs(ans[2])
        if len(ans)==4:
            correctanswerlength=ans[3]
        Sub(a,'tolerance').text=str(tolerance)
        Sub(a,'tolerancetype').text=tolerancetype  #1=relative (set default) 2=nominal
        Sub(a,'correctanswerformat').text=correctanswerformat # 2=sigfigs (set default) 1=decimals
        Sub(a,'correctanswerlength').text=str(correctanswerlength)
    ####
    data=Sub(q,"dataset_definitions")
    for v in var:
        data1=Sub(data,"dataset_definition")
        try:
            if len(v['expression'])>0:
                Sub(Sub(data1,'expression'),"text").text=r"<![CDATA["+v['expression']+"]]>"
                Sub(data1,'order').text=str(v['order'])
        except:
            None
        Sub(Sub(data1,"status"),"text").text="private"
        Sub(Sub(data1,"name"),"text").text=v['name']
        Sub(data1,"type").text='calculatedsimple'
        Sub(Sub(data1,"distribution"),"text").text="uniform"
        Sub(Sub(data1,"minimum"),"text").text=str(v["minmax"][0])
        Sub(Sub(data1,"maximum"),"text").text=str(v["minmax"][1])
        Sub(Sub(data1,"decimals"),"text").text=str(v["decimals"])
        Sub(data1,"itemcount").text=str(len(v["values"]))
        Sub(data1,"number_of_items").text=str(len(v["values"]))
        items=Sub(data1,'dataset_items')
        i=1
        for val in v["values"]:
            item=Sub(items,'dataset_item')
            Sub(item,'number').text=str(i)
            Sub(item,'value').text=str(val)
            i+=1


# In[29]:


def create_truefalse(quiz,name,text,answers):
    q=Sub(quiz,'question')
    q.set('type','truefalse')

    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    ####
    Sub(q,'defaultgrade').text="1.0"
    Sub(q,'penalty').text="0.3333333"
    Sub(q,'hidden').text="0"
    ####
    single=0
    for ans in answers:
        a=Sub(q,'answer')
        if ans[0] in ['true',"True",'TRUE','1']:
            a.set('format','moodle_auto_format')
            Sub(a,'text').text="true"
        elif ans[0] in ['false',"False",'FALSE','0']:
            a.set('format','moodle_auto_format')
            Sub(a,'text').text="false"
        else:
            raise Exception('A true/false question given wrong answers in q: '+name)
        if (ans[1]==100):
            single+=1
            a.set('fraction',"100")
        else:
            a.set('fraction',"0")
    if (single!=1):
        raise Exception('A true/false question should have a single correct answer in q: '+name)


# In[30]:


def create_multichoice(quiz,name,text,answers,single_answer=True,shuffle=True):
    q=Sub(quiz,'question')
    q.set('type','multichoice')

    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    ####
    Sub(q,'defaultgrade').text="1.0"
    Sub(q,'penalty').text="0.3333333"
    Sub(q,'hidden').text="0"
    Sub(q,'answernumbering').text="abc"
    if shuffle:
        Sub(q,'shuffleanswers').text="true"
    else:
        Sub(q,'shuffleanswers').text="false"
    ####
    v=0
    if single_answer:
        Sub(q,'single').text="true"
        for i in answers:
            v=max(v,i[1])
        if (v!=100.0):
            raise Exception('One of your single answers should weigh 100%')
    else:
        Sub(q,'single').text="false"
        for i in answers:
            v+=max(0,i[1])
        if (v<99.99):
            raise Exception('The weights of the answers should add up to 100%')
    ####
    for ans in answers:
        a=Sub(q,'answer')
        a.set('fraction',str(ans[1]))
        a.set('format','html')
        Sub(a,'text').text="<![CDATA["+fix_latex(ans[0])+"]]>"


# In[31]:


def SHORTANSWER(answers):
    v=r"{1:SHORTANSWER:"
    if type(answers)==str:
        return v+"="+answers+r"}"
    else:
        j=0
        for i in answers:
            j+=1
            if type(i)==str:
                if j==1:
                    v+="="+i
                else:
                    v+="~="+i
            elif type(i)==list:
                if j==1:
                    v+="%"+str(i[1])+"%"+i[0]
                else:
                    v+="~%"+str(i[1])+"%"+i[0]
            else:
                raise Exception("Unknown type of answer: "+str(i))
        v+=r"}"
        return v

def MULTICHOICE(correct_answer,wrong_answers):
    v=r"{1:MULTICHOICE_S:="
    v+=correct_answer
    for i in wrong_answers:
        if type(i)==str:
            v+=r"~"+i
        elif type(i)==list:
            v+=r"~%"+str(i[1])+"%"+i[0]
        else:
            raise Exception("Unknown type of answer: "+str(i))
    v+=r"}"
    return v

def NUMERICAL(answer,precision=DEFAULT_TOL,accuracy=0.01,additional_answers=[]):
    acc=0
    if answer==0:
        acc=accuracy
    v=r"{1:NUMERICAL:="+str(answer)+":"+str(precision*answer+acc)
    for a in additional_answers:
        acc=0
        if a[0]==0:
            acc=accuracy
        v+=r"~%"+str(a[1])+"%"+str(a[0])+":"+str(precision*a[0]+acc)
    v+=r"}"
    return v


def create_cloze(quiz,name,text):
    q=Sub(quiz,'question')
    q.set('type','cloze')

    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    ####
    Sub(q,'hidden').text="0"
    Sub(q,'penalty').text="0.3333333"


# In[32]:


#print(NUMERICAL(0,additional_answers=[[3,50],[-7.05,25]]))
#print(SHORTANSWER(["J","joule",["jule",50]]))
#print(SHORTANSWER("J"))
#print(MULTICHOICE("J",["watt","m/s",["j",50]]))


# In[33]:


def create_numerical(quiz,name,text,answers,tolerance=DEFAULT_TOL,accuracy=0.0):
    q=Sub(quiz,'question')
    q.set('type','numerical')

    Sub(Sub(q,'name'),'text').text=name
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    Sub(t,'text').text=text
    ####
    Sub(q,'defaultgrade').text="1"
    Sub(q,'hidden').text="0"
    Sub(q,'penalty').text="0.3333333"
    Sub(q,'unitgradingtype').text="0"
    Sub(q,'unitpenalty').text="0.1000000"
    Sub(q,'showunits').text="3"
    Sub(q,'unitsleft').text="0"
    ###
    if type(answers)!=list:
        answers=[[answers,100]]
    for ans in answers:
        a=Sub(q,'answer')
        a.set('fraction',str(ans[1]))
        a.set('format',"moodle_auto_format")
        Sub(a,'text').text=str(ans[0])
        if len(ans)==3:
            tol=abs(ans[2])
        else:
            tol=abs(tolerance*ans[0]+accuracy)
        Sub(a,'tolerance').text=str(tol)


# In[25]:


def create_missing_words(quiz,name,text,wrong_answers=[],shuffle=True,q_type='gapselect'):
    q=Sub(quiz,'question')
    q.set('type',q_type)
    t=Sub(q,'questiontext')
    t.set('format','html')
    text="<![CDATA[<p>"+fix_latex(text)+"<br></p>]]>"
    text=fix_images(t,text)
    missing_words=extract_arg_of_function(text,"",brackets=["[[","]]"])
    if q_type!='gapselect':
        for w in missing_words:
            if len(w.split('@')[0].split('U'))==1:
                if missing_words.count(w)>1:
                    raise Exception('Word in gapselect/ddwtos question used more than once but set to single use.\nConsider changing it to unlimited use by writing U after the group number.')
    missing_words=list(set(missing_words))
    for i in range(len(missing_words)):
        text=text.replace("[["+missing_words[i]+"]]","[["+str(i+1)+"]]")
    Sub(t,'text').text=text
    Sub(q,'defaultgrade').text="1"
    Sub(q,'hidden').text="0"
    Sub(q,'penalty').text="0.1"
    if shuffle:
        Sub(q,'shuffleanswers').text="1"
    else:
        Sub(q,'shuffleanswers').text="0"
    Sub(Sub(q,'name'),'text').text=name
    #print(wrong_answers)
    all_answers=[]
    for w in missing_words:
        w=w.split("@")
        if q_type=='gapselect':
            n=Sub(q,'selectoption')
        else:
            n=Sub(q,'dragbox')
            if len(w[0].split('U'))==2:
                Sub(n,'infinite')
        Sub(n,'text').text=fix_latex("@".join(w[1:])).strip()
        Sub(n,'group').text=w[0].split('U')[0].strip()
        all_answers.append(str([w[0].split('U')[0].strip(),fix_latex("@".join(w[1:])).strip()]))
    if q_type!='gapselect':
        if len(all_answers)!=len(list(set(all_answers))):
            raise Exception('Correct answer in gapselect/ddwtos question is not consistently set to unlimited/limited use.\nCheck that the group numbers are consistently set to the format #U.')
    for w in wrong_answers:
        if q_type=='gapselect':
            n=Sub(q,'selectoption')
        else:
            n=Sub(q,'dragbox')
            if len(w[0].split('U'))==2:
                Sub(n,'infinite')
        Sub(n,'text').text=fix_latex(w[1]).strip()
        Sub(n,'group').text=w[0].split('U')[0].strip()
        if str([w[0].split('U')[0].strip(),fix_latex(w[1]).strip()]) in all_answers:
            raise Exception('One of the wrong answers in gapselect/ddwtos quesion is identical to one of the correct answers.')


# In[26]:


def write_quiz_to_file(quiz,filename):
    xml=ET.tostring(quiz).decode("ASCII")
    xml=xml.replace("&lt;","<")
    xml=xml.replace("&gt;",">")
    with open(filename, "w") as f:
        f.write(xml)


# # Text to XML

# In[27]:


def extract_line(text,key):
    a=text.split(key)
    res=[]
    for b in a[1:]:
        res.append((b.split("\n")[0]).strip())
    return res


# In[28]:


#text="""(MULTICHOICE("kW",["J","s","m/s","(star)"]), MULTICHOICE("kW","["))"""
def evaluate_cloze_function(text,f):
    args=extract_arg_of_function(text,f)
    for arg in args:
        text=text.replace(f+"("+arg+")",eval(f+"("+arg+")"))
    return text


# In[29]:


def extract_vars(text,N,shared=True):
    if shared==True:
        vv=extract_line(text,"SHARED_VARS:")
    else:
        vv=extract_line(text,"PRIVATE_VARS:")
    #print("LINE: "+str(vv))
    res=[]
    for v1 in vv:
        vv2=v1.split(";")
        for v2 in vv2:
            v3=v2.strip().split("=")
            if (len(v3)==2):
                res.append([v3[0].strip(),v3[1].strip()])

    dic={}
    for r in res:
        try:
            if dic.get(r[0]) == None:
                dic[r[0]]=r[1]
            else:
                raise Exception("Variable defined twice: "+r[0])
        except:
            print(("WARNING! ########################################################## Variable defined twice: "+r[0]))
            continue
    i=0
    for d in dic.keys():
        #for dd in dic.keys():
        #    print(d+"   "+dd +"   "+str(dic[dd]))
        try:
            sig=3
            if dic[d][0]=='{' and dic[d][-1]=='}':
                tmp=dic[d][1:-1].split("sigfigs:")
                dic[d]=tmp[0].strip()
                #print(tmp)
                sig=round(float(tmp[1]))
            if dic[d][0]=='[' and dic[d][-1]==']':
                dic[d]="sample_var('"+d+"',minmax="+dic[d]+",count="+str(N)+",shared="+str(shared)+",sigfigs="+str(sig)+")"
            else:
                dicd=dic[d]
                for d1 in list(dic.keys())[:i]:
                    dic[d]=re.sub(r'\b'+d1+r'\b', "dic[\'"+d1+"\']['values']", dic[d])
                dic[d]="create_var_from_array('"+d+"',"+dic[d]+",expression=\"\"\""+dicd+"\"\"\",shared="+str(shared)+",sigfigs="+str(sig)+",order="+str(i)+")"
            #print(d+"   "+dic[d])
            dic[d]=eval(dic[d])
            #print(d+"   "+str(dic[d]))
        except:
            raise #Exception('There were issues with shared variable: '+d)
        i+=1
        
    return dic

def find_used_vars(string):
    subs=string.split("{")
    arg=[]
    for s in subs[1:]:
        u=s.split("}")[0]
        if not("=" in u):
            arg.append(u)
    return arg


# In[30]:


def strip_latex(text):
    a=text.split("$")
    return "".join(a[0::2])


# In[31]:


def extract_question(quiz,q_text,I,var={},N=200):
    var_=var.copy()
    try:
        
        try:
            text=q_text.split("TEXT:")[1].split("DRAG_DROP:")[0]
        except:
            text=""
        if "MARKDOWN" in q_text:
            try:
                text=markdownToHTML(text)
            except:
                raise
                
        text=text.strip()
            
        q_type=extract_line(q_text,"TYPE:")[0]
        
        name=extract_line(q_text,"NAME:")[0]
        #if q_type!='category':
        #    name="Q"+str(I)+": "+name.strip()
        
        try:
            shuffle=eval(extract_line(q_text,"SHUFFLE:")[0])
        except:
            shuffle=True
        
        #print(q_type+"   "+name)
        
        if q_type=='category':
            create_category(quiz,name.replace("$course$/",""))
        elif q_type=='description':
            create_description(quiz,name,text)
        elif q_type=='ddimageortext':
            dragdrop=q_text.split("DRAG_DROP:")[1].split(r"%%%")[0].strip()
            create_ddimageortext(quiz,name,text,dragdrop,shuffle=shuffle)
        elif q_type=='ddmarker':
            dragdrop=q_text.split("DRAG_DROP:")[1].split(r"%%%")[0].strip()
            showmisplaced=extract_line(q_text,"SHOWMISPLACED:")[0].strip()
            if showmisplaced in ["True",'true','TRUE','1']:
                showmisplaced=True
            else:
                showmisplaced=False
            create_ddmarker(quiz,name,text,dragdrop,shuffle=shuffle,showmisplaced=showmisplaced)
        elif q_type=='shortanswer':
            try:
                case=extract_line(q_text,"CASE:")[0]
            except:
                case="0"
            WA=[r.split("+++") for r in extract_line(q_text,"ANSWER:")]
            #print(WA)
            answers=[[r[1].strip(),float(r[0])] for r in WA]
            create_shortanswer(quiz,name,text,answers,case=case)
        elif q_type=='essay':
            create_essay(quiz,name,text)
        elif q_type=='randomsamatch':
            choose=int(extract_line(q_text,"CHOOSE:")[0])
            if extract_line(q_text,"SUBCATS:")[0] in ['1','True','TRUE','true']:
                subcats=True
            else:
                subcats=False
            create_randomsamatch(quiz,name,text,choose,subcats)
        elif q_type=='matching':
            QA=[r.split("+++") for r in extract_line(q_text,"Q&A:")]
            create_matching(quiz,name,text,QA,shuffle=shuffle)
        elif (q_type in ['calculated_simple','calculated','calculatedsimple','calculatedmulti']):
            try:
                tol=abs(float(extract_line(q_text,"TOLERANCE:")[0]))
            except:
                tol=DEFAULT_TOL
            try:
                correctanswerlength=int(extract_line(q_text,"SIGFIGS:")[0])
            except:
                correctanswerlength=3
            #print(q_text)
            #print(strip_latex(q_text))
            #print(var_)
            var_.update(extract_vars(strip_latex(q_text),N,shared=False))
            #print(var_)
            eq=extract_line(q_text,"EQUATION:")
            eq_str=str(eq)
            if len(eq)>1:
                eq=[[(rr[1].strip()),float(rr[0].strip())]for rr in [r.split("+++") for r in eq]]
            else:
                eq=eq[0]
            var_local=[]
            vs=set(find_used_vars(strip_latex(text))+find_used_vars(eq_str))
            for v in vs:
                try:
                    var_local.append(var_[v])
                except:
                    raise Exception('Variable undefined: '+v)
            if q_type in ['calculated_simple','calculatedsimple']:
                create_calculated_simple(quiz,name,text,eq,var_local,tolerance=tol,correctanswerlength=correctanswerlength)
            if q_type=='calculated':
                create_calculated(quiz,name,text,eq,var_local,tolerance=tol,correctanswerlength=correctanswerlength)
            if q_type=='calculatedmulti':
                try:
                    single_answer=eval(extract_line(q_text,"SINGLE_ANSWER_Q:")[0])
                except:
                    single_answer=True
                create_calculatedmulti(quiz,name,text,eq,var_local,tolerance=tol,correctanswerlength=correctanswerlength,single_answer=single_answer)
        elif q_type=='multichoice':
            try:
                single_answer=eval(extract_line(q_text,"SINGLE_ANSWER_Q:")[0])
            except:
                single_answer=True
            WA=[r.split("+++") for r in extract_line(q_text,"ANSWER:")]
            #print(WA)
            answers=[[r[1].strip(),float(r[0])] for r in WA]
            create_multichoice(quiz,name,text,answers,single_answer=single_answer,shuffle=shuffle)
        elif q_type=='truefalse':
            WA=[r.split("+++") for r in extract_line(q_text,"ANSWER:")]
            #print(WA)
            answers=[[r[1].strip(),float(r[0])] for r in WA]
            create_truefalse(quiz,name,text,answers)
        elif q_type in ["missing_words",'gapselect','ddwtos']:
            if (q_type=='missing_words'):
                q_type='gapselect'
            wrong_answers=[[rr[0].strip(),rr[1].strip()]for rr in [r.split("+++") for r in extract_line(q_text,"CAT&WRONG_ANS:")]]
            create_missing_words(quiz,name,text,wrong_answers,shuffle=shuffle,q_type=q_type)
        elif q_type=="numerical":
            try:
                tol=abs(float(extract_line(q_text,"TOLERANCE:")[0]))
            except:
                tol=DEFAULT_TOL
            try:
                acc=float(extract_line(q_text,"ACCURACY:")[0])
            except:
                acc=DEFAULT_TOL
            answers=extract_line(q_text,"ANSWER:")
            if len(answers)>1:
                answers=[[float(rr[1].strip()),float(rr[0].strip())]for rr in [r.split("+++") for r in answers]]
            else:
                answers=float(answers[0])
            create_numerical(quiz,name,text,answers,tolerance=tol,accuracy=acc)
        elif q_type=="cloze":
            text=evaluate_cloze_function(text,"MULTICHOICE")
            text=evaluate_cloze_function(text,"NUMERICAL")
            text=evaluate_cloze_function(text,"SHORTANSWER")
            create_cloze(quiz,name,text)
        else:
            raise Exception('Unknown question type: '+q_type)
        
    except:
        print("No question here: "+q_text)
        raise


# In[32]:


def text_to_xml(text,xml_file):
    import re
    split="\n[ \t]*----------+\n"
    quiz=Ele('quiz')
    #create_category(quiz,extract_category(text))
    try:
        N_samples=int(extract_line(text,"N_SAMPLES:")[0])
    except:
        N_samples=200
        
       
    Cs=re.split("TYPE:[ \t]*category\n",text)
    #print(Cs)
    if len(Cs)==1:
        #CATs=re.split(split,Cs[0])
        CATs=[re.split(split,Cs[0])[1:]]
    else:
        #CATs=[re.split(split,Cs[0])[:-1]]
        CATs=[]
        for i in range(len(Cs)-1):
            if (i<len(Cs)-2):
                CATs.append([re.split(split,Cs[i])[-1]+"TYPE: 			category"+re.split(split,Cs[i+1])[0]]+
                            re.split(split,Cs[i+1])[1:-1])
            else:
                CATs.append([re.split(split,Cs[i])[-1]+"TYPE: 			category"+re.split(split,Cs[i+1])[0]]+
                            re.split(split,Cs[i+1])[1:])

    for cat in CATs:
        #print("\n".join(cat))
        shared_vars=extract_vars("\n".join(cat),N_samples,shared=True) #separate shared variables in each category
        #print(str(shared_vars))
        i=1
        for q in cat:
            extract_question(quiz,q,i,shared_vars,N_samples)
            i+=1
    write_quiz_to_file(quiz,xml_file)


# # Sorting questions within category in text file

# In[ ]:


def sort_qs_in_text(text):
    end=r"""

   -------------------------------------------------------------

"""
    split="\n[ \t]*----------+\n"
    import re
    #quiz=re.split(split,text)[0]
    Cs=re.split("TYPE:[ \t]*category\n",text)
    quiz=re.split(split,text)[0]
    categ=[]
    if len(Cs)==1:
        #CATs=re.split(split,Cs[0])
        CATs=[re.split(split,Cs[0])[1:]]
    else:
        #CATs=[re.split(split,Cs[0])[:-1]]
        CATs=[]
        
        for i in range(len(Cs)-1):
            if (i<len(Cs)-2):
                categ.append(re.split(split,Cs[i])[-1]+"TYPE: 			category\n"+re.split(split,Cs[i+1])[0])
                CATs.append(
                            re.split(split,Cs[i+1])[1:-1])
            else:
                categ.append(re.split(split,Cs[i])[-1]+"TYPE: 			category\n"+re.split(split,Cs[i+1])[0])
                CATs.append(
                            re.split(split,Cs[i+1])[1:])
    #print(categ)
    from natsort import natsorted

    for cat in CATs:
        cat=natsorted(cat)
        if len(categ)>0:
            quiz+=end+categ.pop(0)
        if len(cat)>0:
            quiz+=end+end.join(cat)
    return quiz


# # XML to text

# In[34]:


def valid_url(s):
    if ("http" in s) and (r"." in s):
        return True
    else:
        return False

import urllib.request
import urllib.parse

def down_image(url):
    filename = url.split("/")[-1]
    filename=urllib.parse.unquote(filename, encoding='utf-8', errors='replace')
    opener=urllib.request.build_opener()
    opener.addheaders=[('User-Agent','Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1941.0 Safari/537.36')]
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(url, filename)
    return filename


# In[35]:


def returnOrder(e):
    return e['order']
def returnName(e):
    return e['name']


# In[36]:


from decimal import Decimal
def count_sigfigs(numstr):
    if type(numstr)==list:
        return [len(Decimal(n).normalize().as_tuple().digits) for n in numstr]
    else:
        return len(Decimal(numstr).normalize().as_tuple().digits)
#np.max(count_sigfigs([str(0.1),str(0.0021)]))


# In[ ]:


def dict_to_md_ddimageortext(doc):
    dg=doc['drag']
    if type(dg)==dict:
        dg=[dg]
    images = [doc]+dg
    if images is not None:
        for image in images:
            try:
                img_name = image['file']['@name'].replace("$","SsS").replace(r"?","QqQ")
                img_data = image['file']['#text']
                with open( img_name, 'wb') as f:
                    f.write(base64.decodebytes(img_data.encode('utf-8')))
            except:
                continue


    drag_choices = doc['drag']
    if type(drag_choices)==dict:
        drag_choices=[drag_choices]
    
    choices=[]
    
    for drag_choice in drag_choices:
        if 'infinite' in drag_choice:
            inf='Yes'
        else:
            inf='No'
        try:
            choices.append({
                'filename': drag_choice['file']['@name'].replace("$","SsS").replace(r"?","QqQ"),
                'group' : str(drag_choice['draggroup']),
                'text' : 'nOtHiNgHeRE',
                'location' : [],
                'inf':inf
            })
        except:
            choices.append({
                'filename': 'nOtHiNgHeRE',
                'group' : str(drag_choice['draggroup']),
                'text' : xml_to_text_deal_with_dollar_signs((drag_choice['text'])),
                'location' : [],
                'inf':inf
            })
    #print(doc)
    drop_answers = doc['drop']
    if type(drop_answers)==dict:
        drop_answers=[drop_answers]
    for drop_answer in drop_answers:
        choices[-1+int(drop_answer['choice'])]['location'].append([drop_answer['xleft'],drop_answer['ytop']])

    main_image_filename = doc['file']['@name'].replace("$","SsS").replace(r"?","QqQ")
    #Converting XML to Markdown
    markdown_text = '   ![](' + main_image_filename + ')\n\n'
    markdown_text += '   | Drop Location | Drag Group | Drag Content | Unlimited Use? |\n'
    markdown_text += '   |:--:|:--:|:--:|:--:|\n'
    for c in choices:
        if len(c['location'])==0:
            markdown_text+='   | | ' + str(c['group']) + " "
            if c['text']=='nOtHiNgHeRE':
                markdown_text+='| ![](' + c['filename'] + ") | "+c['inf']+"|\n"
            else:
                markdown_text+='| ' + c['text'] + " | "+c['inf']+"|\n"
        for i in range(len(c['location'])):
            markdown_text+='   | ' + str(c['location'][i])[1:-1].replace("'","") + " "
            markdown_text+='| ' + str(c['group']) + " "
            if (i==0):
                if c['text']=='nOtHiNgHeRE':
                    markdown_text+='| ![](' + c['filename'] + ") | "+c['inf']+"|\n"
                else:
                    markdown_text+='| ' + c['text'] + " | "+c['inf']+"|\n"
            else:
                markdown_text+='| | |\n'
                if c['inf']=='No':
                    raise Exception('Using a drag item multiple times, but set to non-repeatable.')
            
        
    markdown_text += '\n\n'

    markdown_text += "   %%% Below is a preview that works in Ghostwriter. Not needed when creating a question.\n\n"
    
    markdown_text += '   <div style="position: relative;">\n'
    markdown_text += '   <img src="'+main_image_filename+'"  />\n'
    for c in choices:
        for i in range(len(c['location'])):
            if c['text']=='nOtHiNgHeRE':
                markdown_text+='   <div style="position: absolute; left:'+c['location'][i][0]+'px;top:'+c['location'][i][1]+'px;"><img src="'+c['filename']+'"  /></div>\n'
            else:
                markdown_text+='   <div style="position: absolute; left:'+c['location'][i][0]+'px;top:'+c['location'][i][1]+'px;">'+c['text']+'</div>\n'
    
    markdown_text+='   </div>\n\n'
    
    return markdown_text


# In[ ]:


def dict_to_md_ddmarker(doc):
    dg=doc['drag']
    if type(dg)==dict:
        dg=[dg]
    images = [doc]+dg
    if images is not None:
        for image in images:
            try:
                img_name = image['file']['@name'].replace("$","SsS").replace(r"?","QqQ")
                img_data = image['file']['#text']
                with open( img_name, 'wb') as f:
                    f.write(base64.decodebytes(img_data.encode('utf-8')))
            except:
                continue


    drag_choices = doc['drag']
    if type(drag_choices)==dict:
        drag_choices=[drag_choices]
    
    choices=[]
    
    for drag_choice in drag_choices:
        if 'infinite' in drag_choice:
            inf='Inf'
        else:
            inf=drag_choice['noofdrags']
        choices.append({
                'text' : xml_to_text_deal_with_dollar_signs((drag_choice['text'])),
                'coords' : [],
                'shape' : [],
                'inf':inf
            })
    #print(doc)
    drop_answers = doc['drop']
    if type(drop_answers)==dict:
        drop_answers=[drop_answers]
    for drop_answer in drop_answers:
        choices[-1+int(drop_answer['choice'])]['shape'].append(drop_answer['shape'])
        choices[-1+int(drop_answer['choice'])]['coords'].append(drop_answer['coords'])

    main_image_filename = doc['file']['@name'].replace("$","SsS").replace(r"?","QqQ")
    #Converting XML to Markdown
    markdown_text = '   ![](' + main_image_filename + ')\n\n'
    markdown_text += '   | Drop Shape | Drop Coords | Drag Content | Use # of times (Inf for $\infty$) |\n'
    markdown_text += '   |:--:|:--:|:--:|:--:|\n'
    for c in choices:
        if len(c['shape'])==0:
            markdown_text+='   | | '
            markdown_text+='| ' + c['text'] + " | "+c['inf']+"|\n"
        for i in range(len(c['shape'])):
            markdown_text+='   | ' + str(c['shape'][i]) + " "
            markdown_text+='| ' + str(c['coords'][i]) + " "
            if (i==0):
                markdown_text+='| ' + c['text'] + " | "+c['inf']+"|\n"
            else:
                markdown_text+='| | |\n'
                if c['inf']!='Inf':
                    if int(c['inf'])<i+1:
                        raise Exception('Using a drag item more times than set in Column.')
        
    markdown_text += '\n\n'

    markdown_text += "   %%% Below is a preview that works in Ghostwriter. Not needed when creating a question.\n\n"
    
    markdown_text += '   <div style="position: relative;">\n'
    markdown_text += '   <img src="'+main_image_filename+'"  />\n'
    for c in choices:
        for i in range(len(c['shape'])):
            shape=c['shape'][i]
            coords=c['coords'][i]
            if shape in ["polygon",'p','P','Polygon','POLYGON']:
                markdown_text+=( '   <div style="width:1000px;height:1000px;position:absolute;top: 0;left:0;background-color:rgba(150, 150, 0, 0.5);clip-path: polygon('+
                                coords.replace(',','px ').replace(';','px, ')+'px)"></div>\n')
                coo=eval('['+coords.replace(';','],[')+']')
                coo=np.array(coo)
                markdown_text+='   <h3 style="position:absolute;margin:0;left:'+str(round(coo[:,0].mean()))+'px;top:'+str(round(coo[:,1].min()))+'px">'+c['text']+'</h3>\n'
                markdown_text+='   <!---->\n'
            elif shape in ["rectangle",'r','R','Rectangle','RECTANGLE']:
                coo=eval('['+coords.replace(';','],[')+']')
                coo=np.array(coo)
                markdown_text+='   <div style="position:absolute;left:'+str(coo[0,0])+'px;top:'+str(coo[0,1])+'px;width:'+str(coo[1,0])+'px;height:'+str(coo[1,1])+'px;background-color: rgba(150, 150, 0, 0.5);border-radius: 0%;">\n   <h3 style="position:absolute;text-align:center;margin:auto;left:0;right:0;top:0;bottom:0">'+c['text']+'</h3>\n   </div>\n'
                markdown_text+='   <!---->\n'
            elif shape in ["circle",'Circle','CIRCLE','c',"C"]:
                r=int(coords.split(';')[1])
                coo=[int(i) for i in coords.split(';')[0].split(',')]
                markdown_text+='   <div style="width:1000px;height:1000px;position:absolute;top: 0;left:0;background-color:rgba(150, 150, 0, 0.5);clip-path: circle('+str(r)+'px at '+str(coo[0])+'px ' +str(coo[1])+'px)"></div>\n'
                markdown_text+='   <h3 style="position:absolute;margin:0;left:'+str(coo[0]-r)+'px;top:'+str(coo[1]-r)+'px;">'+c['text']+'</h3>\n'
                markdown_text+='   <!---->\n'
            else:
                raise Exception('Unknown shape mask for drop item.')
    markdown_text+='   </div>\n\n'
    
    return markdown_text


# In[ ]:


def xml_to_text_deal_with_dollar_signs(text):
    text=re.sub(r'([^\$])\$([^\$])', r"\1DOLLAR_SIGN\2", text)
    if len(text)>=2 and text[-1]=="\$" and  text[-2]!="\$":
        text=text[:-1]+"DOLLAR_SIGN"
    text=text.replace(r"\(","$").replace(r"\)","$")
    text=text.replace("$$","$")
    text=text.replace("$$","$")
    return text


# In[1]:


import base64
import time
import html

def xml_to_text(quiz,MARKDOWNIFY=False,save_images=True,fix_ranges_from_database=False):
    TEXT=""
    codespace ="       "    
    end=r"""

   -------------------------------------------------------------

"""
    Qs=[]
    qQz=quiz['question']
    #print(qQz)
    if type(qQz)==dict:
        qQz=[qQz]
    for q in qQz:
        #print(q)
        try:
            try:
                q_name=q['name']['text']
            except:
                None
           
            q_type= q['@type']
            if q_type=="category":
                text=""
                q_name=q['category']['text'].split("$/")[-1]
            else:
                text=q['questiontext']['text']
        
            try:
                img_data=q['questiontext']
                if type(img_data)==dict:
                    img_data=[img_data]
                for img in img_data:
                    im=img['file']
                    if type(im)==dict:
                        im=[im]
                    for i in im:
                        try:
                            filename=i['@name'].decode('ASCII').replace("$","SsS").replace(r"?","QqQ")
                        except:
                            filename=i['@name'].replace("$","SsS").replace(r"?","QqQ")
                        if (save_images):
                            #print(img)
                            if (os.path.isfile(filename)):
                                filename+=str(time.clock_gettime(0)).replace("$","SsS").replace(r"?","QqQ")
                                print("##################################### WARNING: An image file with this name already exists. Saving to: "+filename)
                                print("##################################### WARNING: You will need to manually check the following question: " + q_name)
                            with open(filename, "wb") as fh:
                                fh.write(base64.decodebytes(i['#text'].encode('utf-8')))
            except:
                None

            
            img_data=extract_arg_of_function2(text,r"""<img src="data:image/png;ba""",brackets=["se64,","\""])
            for img in img_data:
                filename=("img_"+str(time.clock_gettime(0))+".png")
                filename=filename.replace("$","SsS").replace(r"?","QqQ")
                if (save_images):
                    with open(filename, "wb") as fh:
                        fh.write(base64.decodebytes(img.encode('utf-8')))
                else:
                    print("##################################### WARNING: An image file was extracted from xml but not saved. In text file it appears as: "+filename)
                    print("##################################### WARNING: You will need to manually check the following question: " + q_name)
                text=text.replace(r"""<img src="data:image/png;base64,"""+img+"\"","<img src=\""+filename+"\"")
            
            
            
            images=extract_arg_of_function2(text,r"",brackets=[r"<img",r">"])
            for im in images:
                filename=extract_arg_of_function2(im,r"src=",brackets=[r'"',r'"'])
                if valid_url(filename[0]):
                    oldf=filename[0]
                    filename=down_image(oldf)
                    if not(filename.split(r".")[-1] in ["png","gif"]):
                        from PIL import Image
                        img = Image.open(filename)
                        filename=filename+".png"
                        filename=urllib.parse.unquote(filename, encoding='utf-8', errors='replace')
                        img.save(filename)
                    try:
                        width=extract_arg_of_function2(im,r"width=",brackets=['"','"'])
                        text=text.replace(r"<img"+im+r">",r"![]("+filename+r"){width="+width[0]+r"}")
                    except:
                        text=text.replace(r"<img"+im+r">",r"![]("+filename+r")")
                else:
                    fn=urllib.parse.unquote(filename[0].replace(r"@@PLUGINFILE@@/",""), encoding='utf-8', errors='replace')
                    fn=fn.replace("$","SsS").split(r"?time")[0].replace(r"?","QqQ")
                    try:
                        width=extract_arg_of_function2(im,r"width=",brackets=['"','"'])
                        text=text.replace(r"<img"+im+r">",r"![]("+fn+r"){width="+width[0]+r"}")
                    except:
                        text=text.replace(r"<img"+im+r">",r"![]("+fn+r")")
        
            
            text=text.replace("\n"," ")
            text=text.replace("  +"," ")
            text=text.replace("\t+"," ")
            #text=text.replace(r"<span>"," ")
            #text=text.replace(r"</span>"," ")
            if not(MARKDOWNIFY):
                text=text.replace("</p>","\n\n")
                text=text.replace("<p>","")
                text=text.replace("<br>","\n\n")
                text=text.replace("<br />","\n\n")
            text=re.sub("\n\n+","\n\n",text).strip()
        
            text=xml_to_text_deal_with_dollar_signs(text)
            if (MARKDOWNIFY):
                text=markdownify(text,escape_underscores=False,escape_asterisks=False)
            
            text = "\n".join([s.strip() for s in text.split("\n")])
            text=text.replace("\n.\n","\n\n")
            text=re.sub("\n\n+","\n\n",text).strip()
            
            text = "\n   ".join([s.strip() for s in text.split("\n")])
            text="   "+text
                
            try:
                shuffle=q['shuffleanswers']
                #print(str(shuffle))
                if shuffle in ["false","False","FALSE","0",0]:
                    shuffle=False
                else:
                    shuffle=True
                #print(str(q['shuffleanswers'])+" "+str(shuffle)+" "+q_name)
            except:
                shuffle=True
            
            if q_type=='ddimageortext':
                Qs.append({'type':q_type,'name':q_name,'text':text,'drag-drop': dict_to_md_ddimageortext(q),'shuffle':shuffle}) 
            elif q_type=='ddmarker':
                showmisplaced=False
                if 'showmisplaced' in q:
                    showmisplaced=True
                Qs.append({'type':q_type,'name':q_name,'text':text,'drag-drop': dict_to_md_ddmarker(q),'shuffle':shuffle,'showmisplaced':showmisplaced}) 
            elif q_type in ['description','cloze','essay','category']:
                #Qs.append([q_type,q_name,text])
                Qs.append({'type':q_type,'name':q_name,'text':text}) #cloze/description
            elif q_type=='randomsamatch':
                Qs.append({'type':q_type,'name':q_name,'text':text,'choose':q['choose'],'subcats':q['subcats']})
            elif q_type =='shortanswer':
                if q['usecase'].strip() in ["0","False","false","FALSE",0]:
                    case="0"
                else:
                    case="1"
                answers=[]
                qq=q['answer']
                if type(qq)==dict:
                    qq=[qq]
                for sub in qq:
                        answer=sub['text']
                        fraction=sub['@fraction']
                        answers.append([answer,float(fraction)])
                Qs.append({'type':q_type,'name':q_name,'text':text,'case':case,'answers':answers})
            elif q_type in ['calculated','calculatedsimple','calculatedmulti']:
                #sync=q.find('./synchronize').text
                answers=[]
                qq=q['answer']
                if type(qq)==dict:
                    qq=[qq]
                for sub in qq:
                        #Sub(a,'tolerance').text=str(tolerance)
                        #Sub(a,'tolerancetype').text=tolerancetype  #1=relative (set default) 2=nominal
                        #Sub(a,'correctanswerformat').text=correctanswerformat # 2=sigfigs (set default) 1=decimals
                        #Sub(a,'correctanswerlength').text=correctanswerlength
                        try:
                            correctanswerlength=int(sub['correctanswerlength'])
                        except:
                            correctanswerlength=3
                        answer=sub['text']
                        tolerance=abs(float(sub['tolerance']))
                        fraction=float(sub['@fraction'])
                        answers.append([answer,fraction,tolerance,correctanswerlength])
                #answer=q.find('./answer/text').text
                vs=q['dataset_definitions']['dataset_definition']
                if type(vs)==dict:
                    vs=[vs]
                var=[]
                for v in vs:
                    #print(v['status'])
                    s=v['status']['text']
                    shared=False
                    if s=='shared':
                        shared=True
                    name=v['name']['text']
                    minmax=[float(v['minimum']['text']),float(v['maximum']['text'])]
                    #print(v.find('decimals/text'))
                    decimals=round(float(v['decimals']['text']))
                    count=int(v['itemcount'])
                    #print(name+'   '+q_name+"   "+str([a for a in v.findall('./dataset_items/')]))
                    try:
                        sigfigs=(np.max(count_sigfigs([a['value'] for a in v['dataset_items']['dataset_item']])))
                    except:
                        sigfigs=1000
                    if (fix_ranges_from_database):
                        minmax_from_data=[(np.min(([float(a['value']) for a in v['dataset_items']['dataset_item']]))),(np.max(([float(a['value']) for a in v['dataset_items']['dataset_item']])))]
                        if (minmax[0]>minmax_from_data[0]) or (minmax[1]<minmax_from_data[1]):
                            print("############ WARNING!!! Mismatch between data min/max and declared m/m in q: "+q_name+" var: "+name+" ["+str(floor_to_sigfigs(minmax_from_data[0],2))
                                 +", "+str(ceil_to_sigfigs(minmax_from_data[1],2))+"]")
                            minmax=[floor_to_sigfigs(minmax_from_data[0],2),ceil_to_sigfigs(minmax_from_data[1],2)]
                        elif (minmax[0]==1.) and (minmax[1]==10.):
                            minmax=[floor_to_sigfigs(minmax_from_data[0],2),ceil_to_sigfigs(minmax_from_data[1],2)]
                        if np.abs(minmax[1]-minmax[0])<1.e-100:
                            minmax[1]=minmax[0]+0.01*np.abs(minmax[1])
                            print("############ WARNING!!! min=max in q: "+q_name+" var: "+name)
                            
                    try:
                        expression=v['expression']['text'].replace(r"<![CDATA[","").replace(r"]]>","")
                        if len(expression)>0:
                            order=int(v['order'])
                            var.append({'name':name,'minmax':minmax,'decimals':decimals,'shared':shared,'expression':expression,'order':order,'sigfigs':sigfigs})
                        else:
                            var.append({'name':name,'minmax':minmax,'decimals':decimals,'shared':shared,'order':0,'sigfigs':sigfigs})
                    except:
                        var.append({'name':name,'minmax':minmax,'decimals':decimals,'shared':shared,'order':0,'sigfigs':sigfigs})
                #Qs.append([q_type,q_name,text,var,answers])
                Qs.append({'type':q_type,'name':q_name,'text':text,'var':var,'answers':answers})#calculated/calculatedsimple
            elif q_type=='matching':
                QA=[]
                qq=q['subquestion']
                if type(qq)==dict:
                    qq=[qq]
                for sub in qq:
                        question=sub['text'].replace('<p dir="ltr" style="text-align: left;">','')
                        answer=sub['answer']['text'].replace('<p dir="ltr" style="text-align: left;">','')
                        question=xml_to_text_deal_with_dollar_signs(question)
                        answer=xml_to_text_deal_with_dollar_signs(answer)
                        QA.append([question.replace(r"<p>","").replace(r"</p>","").replace(r"<br>",""),answer.replace(r"<p>","").replace(r"</p>","").replace(r"<br>","")])
                #Qs.append([q_type,q_name,text,QA,shuffle])
                Qs.append({'type':q_type,'name':q_name,'text':text,'QA':QA,'shuffle':shuffle})#matching
            elif q_type in ['multichoice','truefalse']:
                if (q_type!='truefalse'):
                    if (q['single'].strip() in ["true","True","TRUE","1"]):
                        single_answer=True
                    else:
                        single_answer=False
                else:
                    single_answer=True
                answers=[]
                qq=q['answer']
                if type(qq)==dict:
                    qq=[qq]
                for sub in qq:
                        answer=sub['text'].replace('<p dir="ltr" style="text-align: left;">','')
                        answer=xml_to_text_deal_with_dollar_signs(answer)
                        fraction=sub['@fraction']
                        answers.append([answer.replace("<p>","").replace("</p>","").replace("<br>",""),float(fraction)])
                #Qs.append([q_type,q_name,text,answers,single_answer,shuffle])
                Qs.append({'type':q_type,'name':q_name,'text':text,'answers':answers,'single_answer':single_answer,'shuffle':shuffle})#multichoice
            elif q_type in ['gapselect','ddwtos']:
                answers=[]
                try:
                    qq=q['selectoption']
                except:
                    qq=q['dragbox']
                if type(qq)==dict:
                    qq=[qq]
                for sub in qq:
                        ans=sub['text']
                        ans=xml_to_text_deal_with_dollar_signs(ans)
                        group=sub['group']
                        if 'infinite' in sub:
                            group+='U'
                        answers.append([group,ans])
                z=extract_arg_of_function(text,"\[",brackets=["[","]]"])
                correct_answers=[]
                for zz in z:
                    try:
                        correct_answers.append(int(zz)-1)
                    except:
                        continue
                correct_answers=list(set(correct_answers))
                correct_answers.sort()
                correct_answers.reverse()
                for i in correct_answers:
                    a=answers.pop(i)
                    text=text.replace("[["+str(i+1)+"]]","[["+a[0]+"@"+a[1]+"]]")
                #print(answers)
                wrong_answers=answers
                #Qs.append([q_type,q_name,text,wrong_answers,shuffle])
                Qs.append({'type':q_type,'name':q_name,'text':text,'wrong_answers':wrong_answers,'shuffle':shuffle})#gapselect
                #print(str(shuffle)+" "+q_name+" 1111")
            elif q_type=='numerical':
                answers=[]
                qq=q['answer']
                if type(qq)==dict:
                    qq=[qq]
                for sub in qq:
                        answer=float(sub['text'])
                        tol=float(sub['tolerance'])
                        fraction=float(sub['@fraction'])
                        if abs(answer)<1.e-200:
                            tol=0.01
                        else:
                            tol=abs(tol/(answer))
                        answers.append([answer,fraction,tol])
                Qs.append({'type':q_type,'name':q_name,'text':text,'answers':answers})#numerical
            else:
                raise Exception("Unknown category: "+q_type)
        except:
            raise
            #continue
    TEXT+=codespace + "N_SAMPLES:		200\n"
    
    #print(Qs)
    
    shared_vars=[]
    
    for q in Qs:
        if ((q['type'])=='category'):
            nc=q['name'].count('/')+1
            leading_symbol="#"*nc
        else:
            leading_symbol="1."
            
        TEXT+=end
        #Qs.append({'type':q_type,'name':q_name,'text':text,'answers':answers,'single_answer':single_answer,'shuffle':shuffle})#multichoice
        TEXT+=leading_symbol + " NAME: 			"+q['name']+"\n\n"
        TEXT+=codespace + "TYPE: 			"+q['type']+"\n\n"
        if q['type']=='category':
            shared_vars=[]
        if q['type']=='ddimageortext':
            TEXT+=codespace + "SHUFFLE: 		" + str(q['shuffle'])+"\n\n"
        if q['type']=='ddmarker':
            TEXT+=codespace + "SHUFFLE: 		" + str(q['shuffle'])+"\n\n"
            TEXT+=codespace + "SHOWMISPLACED: 		" + str(q['showmisplaced'])+"\n\n"
            #TEXT+=codespace + "DRAG_DROP:\n"+q['drag-drop']+"\n\n"
        if q['type'] in ['calculated','calculatedsimple','calculatedmulti']:
            #print(q['var'])
            q['var'].sort(key=returnName)
            q['var'].sort(key=returnOrder) 
            #print(q['var'])
            for qvar in q['var']:
                if qvar['shared']:
                    if qvar['name'] in shared_vars:
                        continue
                    else:
                        shared_vars.append(qvar['name'])
                    TEXT+=codespace + 'SHARED_VARS:		'
                else:
                    TEXT+=codespace + 'PRIVATE_VARS:		'
                mm=qvar['minmax']
                if (fix_ranges_from_database):
                    if (np.abs(mm[0])>1.e-100): # and (np.abs(mm[1])>1.e-100):
                        #sigfigs=round(1+np.floor(np.log10(max(abs(mm[0]),np.sqrt(abs(mm[1]))))))+qvar['decimals']
                        sigfigs=round(1+np.floor(1.e-4+np.log10(abs(mm[0]))))+qvar['decimals']
                    elif  np.abs(mm[1])>1.e-100:
                        sigfigs=round(1+np.floor(np.log10((abs(mm[1])))))+qvar['decimals']
                    else:
                        sigfigs=qvar['decimals']
                else:             
                    sigfigs=round(1+np.floor(np.log10(max(abs(mm[0]),abs(mm[1])))))+qvar['decimals']
                if (qvar['sigfigs']==1000):
                    if abs(qvar['sigfigs']-sigfigs)>1:
                        sigfigs=min(qvar['sigfigs'],sigfigs)
                    if (fix_ranges_from_database):
                        if sigfigs==0:
                            sigfigs=1
                        if sigfigs<0: # fix broken sigfigs
                            sigfigs*=-1
                else:
                    sigfigs=qvar['sigfigs']
                try:
                    sss=qvar['expression']
                except:
                    sss=str(qvar['minmax'])
                if (sigfigs!=3):
                    TEXT+=qvar['name']+"={"+sss+" sigfigs:"+str(sigfigs)+"};\n\n"
                else:
                    TEXT+=qvar['name']+"="+sss+";\n\n"
            if len(q['answers'])==1:
                TEXT+=codespace + "EQUATION: 		"+q['answers'][0][0]+"\n\n"
            else:
                for eq in q['answers']:
                    TEXT+=codespace + "EQUATION: 		"+str(eq[1])+"  +++  "+eq[0]+"\n\n"
            TEXT+=codespace + "TOLERANCE: 		"+str(q['answers'][0][2])+"\n\n"
            if q['answers'][0][3]!=3:
                TEXT+=codespace + "SIGFIGS: 		"+str(q['answers'][0][3])+"\n\n"           
        if q['type'] in ['gapselect','ddwtos']:
            TEXT+=codespace + "SHUFFLE: 		" + str(q['shuffle'])+"\n\n"
            #print(q['wrong_answers'])
            for w in q['wrong_answers']:
                TEXT+=codespace + "CAT&WRONG_ANS:  "+w[0]+"  +++  "+w[1]+"\n\n"
        if q['type']=='numerical':
            if len(q['answers'])==1:
                TEXT+=codespace + "ANSWER: 		"+str(q['answers'][0][0])+"\n\n"
                if q['answers'][0][0]==0.0:
                    TEXT+=codespace + "ACCURACY: 		"+str(0.001)+"\n\n"
            else:
                for w in q['answers']:
                    TEXT+=codespace + "ANSWER:  "+str(w[1])+"  +++  "+str(w[0])+"\n\n"
                    if w[0]==0.0:
                        TEXT+=codespace + "ACCURACY: 		"+str(0.001)+"\n\n"
        if q['type']=='matching':
            TEXT+=codespace + "SHUFFLE: 		" + str(q['shuffle'])+"\n\n"
            for w in q['QA']:
                TEXT+=codespace + "Q&A:  "+w[0]+" +++ "+w[1]+"\n\n"
        if q['type']=='multichoice':
            TEXT+=codespace + "SHUFFLE: 		" + str(q['shuffle'])+"\n\n"
            TEXT+=codespace + "SINGLE_ANSWER_Q: 		" + str(q['single_answer'])+"\n\n"
            if len(q['answers'])==1:
                TEXT+=codespace + "ANSWER:		"+q['answers'][0]+"\n\n"
            else:
                for w in q['answers']:
                    TEXT+=codespace + "ANSWER:		"+str(w[1])+" +++ "+w[0]+"\n\n"
        if q['type']=='truefalse':
            if len(q['answers'])==1:
                TEXT+=codespace + "ANSWER:		"+q['answers'][0]+"\n\n"
            else:
                for w in q['answers']:
                    TEXT+=codespace + "ANSWER:		"+str(w[1])+" +++ "+w[0]+"\n\n"
        if q['type']=='shortanswer':
            TEXT+=codespace + "CASE: 		" + q['case']+"\n\n"
            #if len(q['answers'])==1:
            #    TEXT+="ANSWER:		"+q['answers'][0]+"\n"
            #else:
            for w in q['answers']:
                TEXT+=codespace + "ANSWER:		"+str(w[1])+" +++ "+w[0]+"\n\n"
        if q['type']=='randomsamatch':
            if q['subcats'] in ['1','True','TRUE','true']:
                TEXT+=codespace + "SUBCATS:		True\n\n"
            else:
                TEXT+=codespace + "SUBCATS:		False\n\n"
            TEXT+=codespace + "CHOOSE:		"+q['choose']+"\n\n"
                
        if (MARKDOWNIFY):
            TEXT += codespace + "MARKDOWN\n\n"
        #tt=re.sub("\n\n+","\n\n",tt).strip()
        #tt=tt.replace(r"&nbsp;"," ")
        #tt=tt.replace(r"&#160;"," ")
        #tt=tt.replace(r"&#8217;","'")
        #tt=urllib.parse.unquote(tt, encoding='utf-8', errors='replace')
        TEXT += codespace + "TEXT:\n\n"+q['text']+"\n"
        
        if q['type']in ['ddimageortext','ddmarker']:
            #TEXT+=codespace + "SHUFFLE: 		" + str(q['shuffle'])+"\n\n"
            #TEXT+=codespace + "SHOWMISPLACED: 		" + str(q['showmisplaced'])+"\n\n"
            TEXT+="\n"+codespace + "DRAG_DROP:\n\n"+q['drag-drop']+"\n\n"
        
        TEXT = "\n".join([s.rstrip() for s in TEXT.split("\n")])
        TEXT=TEXT.replace("\n.\n","\n\n")
        TEXT=re.sub("\n\n+","\n\n",TEXT).rstrip()
        #print(Qs)
    #import html
    
    TEXT=html.unescape(TEXT)
    #print(TEXT)
    return TEXT


# # Applying xml->text->xml

# In[ ]:


#Importing necessary libraries
import xmltodict
import os
import shutil


def TEXTtoXML(filenameIn,filenameOut,overwrite=False,sort_questions=True):
    if ((not(overwrite)) and (os.path.isfile(filenameOut))):
        print("File already exists. Exiting")
        return
    with open(filenameIn) as f:
        contents = f.read()
    if (sort_questions):
        contents=sort_qs_in_text(contents)
    text_to_xml(contents,filenameOut)
    

def XMLtoTEXT(filenameIn,filenameOut,overwrite=False,sort_questions=True,md=True,save_images=False):
    if ((not(overwrite)) and (os.path.isfile(filenameOut))):
        print("File already exists. Exiting")
        return
    
    with open(filenameIn) as fd:
        quiz_dict = xmltodict.parse(fd.read())
    quiz_dict = quiz_dict['quiz']
    
    #tree = ET.parse(filenameIn)
    #quiz = tree.getroot()

    aa=xml_to_text(quiz_dict,MARKDOWNIFY=md, save_images=save_images)
    if (sort_questions):
        aa=sort_qs_in_text(aa)
    text_file = open(filenameOut, "wt")
    text_file.write(aa)
    text_file.close()


# In[ ]:


#os.chdir('./Astro-DONE/NONE')


# In[ ]:


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('input',type=str,help='input filename')
    parser.add_argument('--output','-o',type=str,help='output filename')
    parser.add_argument('--overwrite', '-rw',action='store_true')
    parser.add_argument('--no_sort_questions', '-sq',action='store_true')
    parser.add_argument('--no_markdown', '-xmd',action='store_true')
    parser.add_argument('--save_images', '-im',action='store_true')
    # Parse arguments from terminal
    args = parser.parse_args()

    filenameIn=args.input
    try:
        filenameOut=args.output
    except:
        None
    overwrite=args.overwrite
    sort_questions=not((args.no_sort_questions))
    md=not((args.no_markdown))
    save_images=args.save_images
    #print(overwrite)
    #print(filenameIn)
    #print(filenameOut)
    if filenameIn[-3:]=="xml":
        if (filenameOut)==None:
            filenameOut=filenameIn[:-3]+"md"
        XMLtoTEXT(filenameIn,filenameOut,overwrite=overwrite,sort_questions=sort_questions,md=md,save_images=save_images)
    if filenameIn[-2:]=="md":
        if (filenameOut)==None:
            filenameOut=filenameIn[:-2]+"xml"
        TEXTtoXML(filenameIn,filenameOut,overwrite=overwrite,sort_questions=sort_questions)
    if filenameIn[-3:]=="txt":
        if len(filenameOut)==0:
            filenameOut=filenameIn[:-3]+"xml"
        TEXTtoXML(filenameIn,filenameOut,overwrite=overwrite,sort_questions=sort_questions)


