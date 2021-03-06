# This is taken from http://code.activestate.com/recipes/573463/
# Original Author: Cory Fabre
# License: PSF
#
# I've modified it to make it work with python >=2.6 ~Thomas

import io

from xml.etree import ElementTree


class XmlDictObject(dict):
    """ Adds object like functionality to the standard dictionary.
    """

    def __init__(self, initdict=None):
        if initdict is None:
            initdict = {}
        super(XmlDictObject).__init__(initdict)
    
    def __getattr__(self, item):
        return self.__getitem__(item)
    
    def __setattr__(self, item, value):
        self.__setitem__(item, value)
    
    def __str__(self):
        if '_text' in self:
            return self.__getitem__('_text')
        else:
            return ''

    @staticmethod
    def wrap(x):
        """ Static method to wrap a dictionary recursively as an XmlDictObject
        """
        if isinstance(x, dict):
            return XmlDictObject({k: XmlDictObject.wrap(v) for (k, v) in x.items()})
        elif isinstance(x, list):
            return [XmlDictObject.wrap(v) for v in x]
        else:
            return x

    @staticmethod
    def __unwrap(x):
        if isinstance(x, dict):
            return {k: XmlDictObject.unwrap(v) for (k, v) in x.items()}
        elif isinstance(x, list):
            return [XmlDictObject.unwrap(v) for v in x]
        else:
            return x
        
    def unwrap(self):
        """ Recursively converts an XmlDictObject to a standard dictionary and returns the result.
        """
        return XmlDictObject.__unwrap(self)


def _ConvertDictToXmlRecurse(parent, dictitem):
    assert type(dictitem) is not type([])

    if isinstance(dictitem, dict):
        for (tag, child) in dictitem.items():
            if str(tag) == '_text':
                parent.text = str(child)

            elif type(child) is type([]):
                # iterate through the array and convert
                for listchild in child:
                    elem = ElementTree.Element(tag)
                    parent.append(elem)
                    _ConvertDictToXmlRecurse(elem, listchild)

            else:                
                elem = ElementTree.Element(tag)
                parent.append(elem)
                _ConvertDictToXmlRecurse(elem, child)
    else:
        parent.text = str(dictitem)


def ConvertDictToXml(xmldict):
    """ Converts a dictionary to an XML ElementTree Element
    """
    roottag = list(xmldict.keys())[0]
    root = ElementTree.Element(roottag)
    _ConvertDictToXmlRecurse(root, xmldict[roottag])
    return root


def _ConvertXmlToDictRecurse(node, dictclass):
    nodedict = dictclass()
    
    if len(node.items()) > 0:
        # if we have attributes, set them
        nodedict.update(dict(node.items()))
    
    for child in node:
        # recursively add the element's children
        newitem = _ConvertXmlToDictRecurse(child, dictclass)
        if child.tag in nodedict:
            # found duplicate tag, force a list
            if type(nodedict[child.tag]) is type([]):
                # append to existing list
                nodedict[child.tag].append(newitem)
            else:
                # convert to list
                nodedict[child.tag] = [nodedict[child.tag], newitem]
        else:
            # only one, directly set the dictionary
            nodedict[child.tag] = newitem

    if node.text is None: 
        text = ''
    else: 
        text = node.text.strip()
    
    if len(nodedict) > 0:            
        # if we have a dictionary add the text as a dictionary value (if there is any)
        if len(text) > 0:
            nodedict['_text'] = text
    else:
        # if we don't have child nodes or attributes, just set the text
        nodedict = text

    return nodedict


def ConvertXmlToDict(root, dictclass=XmlDictObject):
    """ Converts an XML file or ElementTree Element to a dictionary
    """
    if isinstance(root, bytes):
        root = root.decode('utf-8')

    # If a string is passed in, try to open it as a file
    if isinstance(root, str):
        root = io.StringIO(root)
        root = ElementTree.parse(root).getroot()
    elif not ElementTree.iselement(root):
        raise TypeError('Expected ElementTree.Element or file path string. Got: (%s, %s)' % (type(root), root))

    return dictclass({root.tag: _ConvertXmlToDictRecurse(root, dictclass)})
