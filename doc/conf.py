#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Qubes Admin client documentation build configuration file, created by
# sphinx-quickstart on Thu May 11 19:00:43 2017.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import subprocess
sys.path.insert(0, os.path.abspath('..'))

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.viewcode',
]

try:
    import qubesadmin.tools.dochelpers
    extensions.append('qubesadmin.tools.dochelpers')
except ImportError:
    pass

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The encoding of source files.
#
# source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'Qubes Admin client'
copyright = '2017, Invisible Things Lab'
author = 'Invisible Things Lab'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = open('../version').read().strip()
# The full version, including alpha/beta/rc tags.
try:
    release = subprocess.check_output(['git', 'describe', '--long', '--dirty']).strip().decode()
except:
    release = "1"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = 'en'

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#
# today = ''
#
# Else, today_fmt is used as the format for a strftime call.
#
# today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The reST default role (used for this markup: `text`) to use for all
# documents.
#
# default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#
# add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#
# show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
# modindex_common_prefix = []

# If true, keep warnings as "system message" paragraphs in the built documents.
# keep_warnings = False

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True


# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
#html_theme = 'alabaster'
html_theme = 'nature'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
# html_theme_path = []

# The name for this set of Sphinx documents.
# "<project> v<release> documentation" by default.
#
# html_title = 'Qubes Admin client v4.0.0'

# A shorter title for the navigation bar.  Default is the same as html_title.
#
# html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
#
# html_logo = None

# The name of an image file (relative to this directory) to use as a favicon of
# the docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#
# html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Add any extra paths that contain custom files (such as robots.txt or
# .htaccess) here, relative to this directory. These files are copied
# directly to the root of the documentation.
#
# html_extra_path = []

# If not None, a 'Last updated on:' timestamp is inserted at every page
# bottom, using the given strftime format.
# The empty string is equivalent to '%b %d, %Y'.
#
# html_last_updated_fmt = None

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#
# html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#
# html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#
# html_additional_pages = {}

# If false, no module index is generated.
#
# html_domain_indices = True

# If false, no index is generated.
#
# html_use_index = True

# If true, the index is split into individual pages for each letter.
#
# html_split_index = False

# If true, links to the reST sources are added to the pages.
#
# html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
#
# html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
#
# html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#
# html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
# html_file_suffix = None

# Language to be used for generating the HTML full-text search index.
# Sphinx supports the following languages:
#   'da', 'de', 'en', 'es', 'fi', 'fr', 'h', 'it', 'ja'
#   'nl', 'no', 'pt', 'ro', 'r', 'sv', 'tr', 'zh'
#
# html_search_language = 'en'

# A dictionary with options for the search language support, empty by default.
# 'ja' uses this config value.
# 'zh' user can custom change `jieba` dictionary path.
#
# html_search_options = {'type': 'default'}

# The name of a javascript file (relative to the configuration directory) that
# implements a search results scorer. If empty, the default will be used.
#
# html_search_scorer = 'scorer.js'

# Output file base name for HTML help builder.
htmlhelp_basename = 'QubesAdminclientdoc'

# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
     # The paper size ('letterpaper' or 'a4paper').
     #
     # 'papersize': 'letterpaper',

     # The font size ('10pt', '11pt' or '12pt').
     #
     # 'pointsize': '10pt',

     # Additional stuff for the LaTeX preamble.
     #
     # 'preamble': '',

     # Latex figure (float) alignment
     #
     # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'QubesAdminclient.tex', 'Qubes Admin client Documentation',
     'Invisible Things Lab', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#
# latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#
# latex_use_parts = False

# If true, show page references after internal links.
#
# latex_show_pagerefs = False

# If true, show URL addresses after external links.
#
# latex_show_urls = False

# Documents to append as an appendix to all manuals.
#
# latex_appendices = []

# It false, will not define \strong, \code, 	itleref, \crossref ... but only
# \sphinxstrong, ..., \sphinxtitleref, ... To help avoid clash with user added
# packages.
#
# latex_keep_old_macro_names = True

# If false, no module index is generated.
#
# latex_domain_indices = True


# -- Options for manual page output ---------------------------------------

# authors should be empty and authors should be specified in each man page,
# because html builder will omit them
_man_pages_author = []

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('manpages/qvm-backup-restore', 'qvm-backup-restore',
        u'Restores Qubes VMs from backup', _man_pages_author, 1),
    ('manpages/qvm-backup', 'qvm-backup',
        u'Create backup of specified qubes', _man_pages_author, 1),
    ('manpages/qvm-check', 'qvm-check',
        u'Check existence/state of a qube', _man_pages_author, 1),
    ('manpages/qvm-clone', 'qvm-clone',
        u'Clones an existing qube by copying all its disk files', _man_pages_author, 1),
    ('manpages/qvm-create', 'qvm-create',
        u'Creates a new qube', _man_pages_author, 1),
    ('manpages/qvm-device', 'qvm-device',
        u'List/set VM devices', _man_pages_author, 1),
    ('manpages/qvm-features', 'qvm-features',
        u'Manage VM features', _man_pages_author, 1),
    ('manpages/qvm-firewall', 'qvm-firewall',
        u'Qubes firewall configuration', _man_pages_author, 1),
    ('manpages/qvm-kill', 'qvm-kill',
        u'Kill the specified qube', _man_pages_author, 1),
    ('manpages/qvm-ls', 'qvm-ls',
        u'List VMs and various information about them', _man_pages_author, 1),
    ('manpages/qvm-notes', 'qvm-notes',
        u'Manipulate qube notes', _man_pages_author, 1),
    ('manpages/qvm-pause', 'qvm-pause',
        u'Pause a specified qube(s)', _man_pages_author, 1),
    ('manpages/qvm-pool', 'qvm-pool',
        u'Manages Qubes pools and their options', _man_pages_author, 1),
    ('manpages/qvm-prefs', 'qvm-prefs',
        u'List/set various per-VM properties', _man_pages_author, 1),
    ('manpages/qvm-remove', 'qvm-remove',
        u'Remove a VM', _man_pages_author, 1),
    ('manpages/qvm-run', 'qvm-run',
        u'Run a command on a specified VM', _man_pages_author, 1),
    ('manpages/qvm-service', 'qvm-service',
        u'Manage (Qubes-specific) services started in VM', _man_pages_author, 1),
    ('manpages/qvm-shutdown', 'qvm-shutdown',
        u'Gracefully shut down a qube', _man_pages_author, 1),
    ('manpages/qvm-start-daemon', 'qvm-start-daemon',
        u'Start GUI/AUDIO daemon for qubes', _man_pages_author, 1),
    ('manpages/qvm-start', 'qvm-start',
        u'Start a specified qube', _man_pages_author, 1),
    ('manpages/qvm-tags', 'qvm-tags',
        u'Manage tags on a qube', _man_pages_author, 1),
    ('manpages/qvm-template', 'qvm-template',
        u'Manage templates', _man_pages_author, 1),
    ('manpages/qvm-unpause', 'qvm-unpause',
        u'Pause a qube', _man_pages_author, 1),
    ('manpages/qvm-volume', 'qvm-volume',
        u'Manage storage volumes of a qube', _man_pages_author, 1),
    ('manpages/qubes-prefs', 'qubes-prefs',
        u'Display system-wide Qubes settings', _man_pages_author, 1),
]

# If true, show URL addresses after external links.
#
# man_show_urls = False


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc, 'QubesAdminclient', 'Qubes Admin client Documentation',
     author, 'QubesAdminclient', 'One line description of project.',
     'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#
# texinfo_appendices = []

# If false, no module index is generated.
#
# texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#
# texinfo_show_urls = 'footnote'

# If true, do not generate a @detailmenu in the "Top" node's menu.
#
# texinfo_no_detailmenu = False
