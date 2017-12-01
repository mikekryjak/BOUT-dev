#!/usr/bin/env python3

from __future__ import print_function

try:
    from builtins import object
except ImportError:
    pass

from copy import deepcopy as copy


class braces(object):
    def __init__(self, string=""):
        print("%s{" % string)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("}")


class Field(object):
    """A class to keep all the data of the different fields
    """
    # name of the field, e.g. Field3D
    fieldname = ''
    # array: dimensions of the field
    dimensions = []
    # identifier - short version of the field e.g. f3d
    i = ''
    # name of this field
    name = None

    def __init__(self, name, dirs, idn):
        self.fieldname = name
        self.dimensions = dirs
        self.i = idn
        self.name = None

    def getPass(self, const=True, data=False):
        """How to pass data

        Inputs
        ======
        const: Should it be const?
        data:  Pass the raw data?

        """

        ret = ""
        if const:
            ret += "const "
        if self.i == 'real':
            ret += "BoutReal"
        else:
            if data:
                if for_gcc:  # use restrict gcc extension
                    ret += 'BoutReal * __restrict__'
                else:
                    ret += 'BoutReal *'
            else:
                ret += '%s &' % (self.fieldname)
        ret += " %s" % self.name
        return ret

    def get(self, data=True, ptr=False):
        """How to get value from field

        Inputs
        ======
        data: use x,y,z access on raw data?
        ptr:  Do return pointer instead of data

        """

        if self.i == 'real':
            return self.name
        ret = ''
        if ptr:
            ret = "&"
        if data:
            if self.i == 'f2d':
                return ret + '%s[y+x*ny]' % self.name
            elif self.i == 'fp':
                return ret + '%s[z+x*nz]' % self.name
            elif self.i == 'f3d':
                return ret + '%s[z+nz*(y+ny*x)]' % (self.name)
            else:
                return NotImplemented
        else:
            return ret + "%s[i]" % self.name

    def dims(self):
        """Return the dimensions
        """
        return self.dimensions

    def __eq__(self, other):
        try:
            return self.i == other.i
        except AttributeError:
            return self.i == other

    def __ne__(self, other):
        return not (self == other)

    def __str__(self):
        return "Name: %s\nfieldname: %s\n" % (self.name, self.fieldname)

    def setName(self, name):
        self.name = name


# Declare what fields we currently support:
# Field perp is currently missing
f3d = Field('Field3D', ['x', 'y', 'z'], 'f3d')
f2d = Field('Field2D', ['x', 'y'], 'f2d')
real = Field('BoutReal', [], 'real')
fields = [f3d, f2d, real]


def returnType(f1, f2):
    """Determine a suitable return type, by seeing which field is 'larger'.

    """
    if f1 == f2:
        return copy(f1)
    elif f1.i == 'real':
        return copy(f2)
    elif f2.i == 'real':
        return copy(f1)
    else:
        return copy(f3d)


def mymin(f1, f2):
    """Return which of f1, f2 has the least number of dimensions

    """
    if (len(f1.dimensions) < len(f2.dimensions)):
        return f1
    else:
        return f2


# The arthimetic operators
operators = {
    '*': 'mul',
    '/': 'div',
    '+': 'plus',
    '-': 'minus',
}


def low_level_function_generator(operator, operator_name, args):
    """Generate the function that operates on the underlying data

    """

    out, lhs, rhs = args

    print(autogen_warn)
    print("// Do the actual %s of %s and %s" %
          (operator_name, lhs.fieldname, rhs.fieldname))
    print('void autogen_%s_%s_%s_%s(' %
          (out.fieldname, lhs.fieldname, rhs.fieldname, operator_name), end=' ')

    # the first element (intent out) shouldn't be const, the
    # rest should be (intent in)
    const = False
    for f in args:
        print(f.getPass(const=const, data=True), ',', end=' ')
        # first not const, but the remaining ones should be
        const = True
    # depending on how we loop over the fields, we need to now
    # x,y and z, or just the total number of elements
    if elementwise:
        c = ''
        for d in out.dimensions:
            print('%s int n%s' % (c, d), end=' ')
            c = ','
    else:
        print(' int len', end=' ')
    print(')')

    with braces():
        if elementwise:
            # we need to loop over all dimension of the out file
            dims = {"n" + x: x for x in out.dims()}
        else:
            dims = {"len": 'i'}
        for d, i in dims.items():
            print('  for (int %s=0;%s<%s;++%s)' % (i, i, d, i))
        with braces():
            print("    %s = %s %s %s;" % (out.get(data=elementwise),
                                          lhs.get(data=elementwise),
                                          operator,
                                          rhs.get(data=elementwise)))


def high_level_function_generator(operator, operator_name, args):
    """
    It takes the Field objects. This function is doing some high
    level stuff, but does not modify the underlaying data.
    Stuff done here:
     * conserve the mesh
     * conserve the field location
     * check the input & output data
     * allocate data
     * get the underlaying data for the low-level operation
    """

    out, lhs, rhs = args

    print(autogen_warn)
    print("// Provide the C++ wrapper for %s of %s and %s" %
          (operator_name, lhs.fieldname, rhs.fieldname))
    print("%s operator%s(%s,%s)" %
          (out.fieldname, operator, lhs.getPass(), rhs.getPass()))
    with braces():
        print("  Indices i{0,0,0};")
        print("  Mesh *localmesh = %s.getMesh();" %
              ("lhs" if not lhs.i == 'real' else "rhs"))
        if lhs.i != 'real' and rhs.i != 'real':
            print("  ASSERT1(localmesh == rhs.getMesh());")
        print("  %s result(localmesh);" % out.fieldname)
        print("  result.allocate();")
        print("  checkData(lhs);")
        print("  checkData(rhs);")
        # call the C function to do the work.
        print("  autogen_%s_%s_%s_%s("
              % (out.fieldname, lhs.fieldname, rhs.fieldname,
                 operator_name), end=' ')
        for f in args:
            print("%s, " % (f.get(data=False, ptr=True)), end=' ')
        m = ''
        print('\n             ', end=' ')
        for d in out.dimensions:
            print(m, "localmesh->LocalN%s" % d, end=' ')
            if elementwise:
                m = ','
            else:
                m = '*'
        print(");")
        # hardcode to only check field location for Field 3D
        if lhs.i == rhs.i == 'f3d':
            print("#if CHECK > 0")
            with braces("  if (lhs.getLocation() != rhs.getLocation())"):
                print(
                    '    throw BoutException("Trying to %s fields of different locations. lhs is at %%s, rhs is at %%s!",strLocation(lhs.getLocation()),strLocation(rhs.getLocation()));' % operator_name)
            print('#endif')
        # Set out location (again, only for f3d)
        if out.i == 'f3d':
            if rhs.i == 'f3d':
                src = 'rhs'
            elif lhs.i != 'real':
                src = 'lhs'
            else:
                src = 'rhs'
            print("  result.setLocation(%s.getLocation());" % src)
        # Check result and return
        print("  checkData(result);")
        print("  return result;")
    print()
    print()


def low_level_inplace_function_generator(operator, operator_name, lhs, rhs):
    """
    This function operates on the underlying data
    """
    print(autogen_warn)
    print("// Provide the C function to update %s by %s with %s" %
          (lhs.fieldname, operator_name, rhs.fieldname))
    print('void autogen_%s_%s_%s(' %
          (lhs.fieldname, rhs.fieldname, operator_name), end=' ')
    const = False
    fs = [lhs, rhs]
    for f in fs:
        print(f.getPass(data=True, const=const), ",", end=' ')
        const = True
    if elementwise:
        c = ''
        for d in out.dimensions:
            print('%s int n%s' % (c, d), end=' ')
            c = ','
    else:
        print(' int len', end=' ')
    print(')')

    with braces():
        if elementwise:
            # we need to loop over all dimension of the out file
            dims = {"n" + x: x for x in out.dims()}
        else:
            dims = {"len": 'i'}
        for d, i in dims.items():
            print('  for (int %s=0;%s<%s;++%s)' % (i, i, d, i))
        with braces():
            print("    %s %s= %s;" % (lhs.get(data=elementwise),
                                      operator,
                                      rhs.get(data=elementwise)))


def high_level_inplace_function_generator(operator, operator_name, lhs, rhs):
    """
    It takes the Field objects. This function is doing some high
    level stuff, but does not modify the underlaying data.
    Stuff done here:
     * conserve the mesh
     * conserve the field location
     * check the input & output data
     * allocate data
     * get the underlaying data for the low-level operation
    """
    print(autogen_warn)
    print("// Provide the C++ operator to update %s by %s with %s" %
          (lhs.fieldname, operator_name, rhs.fieldname))
    print("%s & %s::operator %s=" %
          (lhs.fieldname, lhs.fieldname, operator), end=' ')
    print("(%s)" % (rhs.getPass(const=True)))
    with braces():
        print("  // only if data is unique we update the field")
        print("  // otherwise just call the non-inplace version")
        with braces("  if (data.unique())"):
            print("    Indices i{0,0,0};")
            if not rhs.i == 'real':
                print("    ASSERT1(fieldmesh == rhs.getMesh());")
            print("    checkData(*this);")
            print("    checkData(rhs);")
            print("    autogen_%s_%s_%s(&(*this)[i]," %
                  (lhs.fieldname, rhs.fieldname, operator_name), end=' ')
            print(rhs.get(ptr=True, data=False), ',', end=' ')
            m = ''
            print('\n             ', end=' ')
            for d in out.dimensions:
                print(m, "fieldmesh->LocalN%s" % d, end=' ')
                if elementwise:
                    m = ','
                else:
                    m = '*'
            print(");")
            # if both are f3d, make sure they are in the same location
            if lhs.i == rhs.i == 'f3d':
                print("#if CHECK > 0")
                with braces("  if (this->getLocation() != rhs.getLocation())"):
                    print('    throw BoutException("Trying to %s fields of different locations!");'
                          % operator_name)
                print('#endif')
                print("    checkData(*this);")
        with braces(" else "):  # if data is not unique
            print("    (*this)= (*this) %s rhs;" % operator)
        print("  return *this;")
    print()
    print()


if __name__ == "__main__":
    for_gcc = True
    autogen_warn = "// This file is autogenerated - see gen_fieldops.py"
    print(autogen_warn)
    print("""#include <field3d.hxx>
    #include <field2d.hxx>
    #include <bout/mesh.hxx>
    #include <globals.hxx>
    #include <interpolation.hxx>
    """)

    # loop over all fields for lhs and rhs of the operation. Generates the
    # not-in-place variants of the operations, returning a new field.
    for lhs in fields:
        for rhs in fields:
            # we don't have define real real operations
            if lhs.i == rhs.i == 'real':
                continue
            rhs = copy(rhs)
            lhs = copy(lhs)
            # if both fields are the same, or one of them is real, we
            # don't need to care what element is stored where, but can
            # just loop directly over everything, using a simple c-style
            # for loop. Otherwise we need x,y,z of the fields.
            if (lhs != rhs and mymin(lhs, rhs).i != 'real'):
                elementwise = True
            else:
                elementwise = False
            # the output of the operation. The `larger` of the two fields.
            out = returnType(rhs, lhs)
            for operator, operator_name in operators.items():

                out.name = 'result'
                lhs.name = 'lhs'
                rhs.name = 'rhs'
                args = [out, lhs, rhs]

                low_level_function_generator(operator, operator_name, args)

                high_level_function_generator(operator, operator_name, args)

    # generate the operators for updating the lhs in place
    for lhs in fields:
        for rhs in fields:
            # no real real operation
            if lhs.i == rhs.i == 'real':
                continue
            if (lhs != rhs and mymin(lhs, rhs).i != 'real'):
                elementwise = True
            else:
                elementwise = False
            lhs = copy(lhs)
            rhs = copy(rhs)
            out = returnType(rhs, lhs)
            out.name = 'result'
            lhs.name = 'lhs'
            rhs.name = 'rhs'
            if out == lhs:
                for operator, operator_name in operators.items():

                    low_level_inplace_function_generator(operator, operator_name,
                                                         lhs, rhs)

                    high_level_inplace_function_generator(operator, operator_name,
                                                          lhs, rhs)
