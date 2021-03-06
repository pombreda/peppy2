======
Peppy2
======



Abstract
========

peppy - (ap)Proximated (X)Emacs Powered by Python

A full-featured editor for text files and more, Peppy provides an XEmacs-like
multi-window/multi-tabbed user interface and is written in and extensible
through Python.  It is built around the emacs concept of major modes --
different views are presented to the user depending on the type of data being
edited.

It is a rewrite of the original peppy, now based on the Enthought Tasks
framework instead of my old custom framework.  (Note that only wxPython is
supported as a GUI backend).  The architectural goal is to provide a system
with low coupling in order to reduce the work required to extend the editor
with new major modes, minor modes, and sidebars.


Goal For Rewrite
================

Why a rewrite of the original peppy_ (which I'll call peppy1 even though it
never got to a 1.0 release)?

.. _peppy: http://peppy.flipturn.org

* **Simplify the code.**
  Peppy1 had the ability to have any major mode in any window, but this needed
  a lot of code to support minor modes switching in and out as tabs changed.
  I got it to work and all, but the code was quite convoluted.  Peppy2 only
  allows similar major modes in a window, and different major modes require
  a new window.  Not a huge inconvenience but saves a considerable amount of
  coding, so I'm happy with this tradeoff.  It allows me to use the Enthought
  Tasks framework pretty much as-is.

* **Make it easier for others to contribute.**
  Peppy1 was using my own framework which had a steep learning curve.
  Hopefully by moving to Enthought's framework, it will have a broader appeal.

* **Leverage other people's code.**
  I wrote a lot of custom code for stuff that I needed at the time, but now
  there are similar packages that others support and maintain.  For example,
  I wrote a virtual file system implementation that worked, but was a whole
  project in itself.  In the intervening years, PyFilesystem_ was written,
  removing the need for me to use my own code.

.. _PyFilesystem: http://packages.python.org/fs/index.html


Prerequisites
=============

python 2.7 (but not 3.x yet)
wxPython 2.9.x (but not 3.0 yet)

The Enthought framework is a custom build for peppy because I've enabled
current support for wx.  Enthought is transitioning to Qt is their primary GUI
toolkit and their wx support has been limited recently.  Fortunately Enthought
was designed to be toolkit agnostic and it was relatively easy to bring their
libraries up to date as compared to Qt.  My patches have not made it back to
Enthought yet, which is why I'm requiring the custom build::

    cd ~/src/enthought
    for name in traits; do echo $name; git clone https://github.com/enthought/$name.git; cd $name; python setup.py develop; cd ..; done
    for name in pyface traitsui; do echo $name; git clone https://github.com/robmcmullen/$name.git; cd $name; python setup.py develop; cd ..; done
    for name in apptools; do echo $name; git clone https://github.com/enthought/$name.git; cd $name; python setup.py develop; cd ..; done
    for name in envisage; do echo $name; git clone https://github.com/robmcmullen/$name.git; cd $name; python setup.py develop; cd ..; done

Or, if you already have all the code checked out and want to build for a new
version of python, you can use::

    for name in traits pyface traitsui apptools envisage; do cd $name; python setup.py develop; cd ..; done


Virtualenv Setup
================

virtualenv /data/virtualenv/wx3
source $VIRTUAL_ENV/bin/activate
mkdir src
cd src
tar xvf /opt/download/wxPython-src-3.0.1.1.tar.bz2 
cd wxPython-src-3.0.1.1/
./configure --prefix=$VIRTUAL_ENV
make -j 8
make install
cat <<EOF >> $VIRTUAL_ENV/bin/activate
LD_LIBRARY_PATH="$VIRTUAL_ENV/lib:$LD_LIBRARY_PATH"
export LD_LIBRARY_PATH
EOF
cd wxPython
python setup.py install
# cd demo/
# python demo.py 



Running The Program
===================

This is still alpha software, so caveat emptor.  The only way to get it currently is to clone it from git::

    $ git clone https://github.com/robmcmullen/peppy2.git
    $ cd peppy2
    $ python run.py


Plugins
=======

Peppy is extended by plugins.  Plugins are based on the `Enthought Framework`__
and are discovered using setuptools plugins.

__ http://docs.enthought.com/envisage/envisage_core_documentation/index.html


Disclaimer
==========

peppy, (ap)Proximated (X)Emacs Powered by Python
Copyright (c) 2006-2014 Rob McMullen (robm@users.sourceforge.net)

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
