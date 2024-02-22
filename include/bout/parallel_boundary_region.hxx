#ifndef __PAR_BNDRY_H__
#define __PAR_BNDRY_H__

#include "bout/boundary_region.hxx"
#include "bout/bout_types.hxx"
#include <vector>

#include <bout/field3d.hxx>
#include <bout/mesh.hxx>

/**
 * Boundary region for parallel direction. This contains a vector of points that are
 * inside the boundary.
 *
 */

namespace parallel_stencil {
// generated by src/mesh/parallel_boundary_stencil.cxx.py
inline BoutReal pow(BoutReal val, int exp) {
  // constexpr int expval = exp;
  // static_assert(expval == 2 or expval == 3, "This pow is only for exponent 2 or 3");
  if (exp == 2) {
    return val * val;
  }
  ASSERT3(exp == 3);
  return val * val * val;
}
inline BoutReal dirichlet_o1(BoutReal UNUSED(spacing0), BoutReal value0) {
  return value0;
}
inline BoutReal dirichlet_o2(BoutReal spacing0, BoutReal value0, BoutReal spacing1,
                             BoutReal value1) {
  return (spacing0 * value1 - spacing1 * value0) / (spacing0 - spacing1);
}
inline BoutReal neumann_o2(BoutReal UNUSED(spacing0), BoutReal value0, BoutReal spacing1,
                           BoutReal value1) {
  return -spacing1 * value0 + value1;
}
inline BoutReal dirichlet_o3(BoutReal spacing0, BoutReal value0, BoutReal spacing1,
                             BoutReal value1, BoutReal spacing2, BoutReal value2) {
  return (pow(spacing0, 2) * spacing1 * value2 - pow(spacing0, 2) * spacing2 * value1
          - spacing0 * pow(spacing1, 2) * value2 + spacing0 * pow(spacing2, 2) * value1
          + pow(spacing1, 2) * spacing2 * value0 - spacing1 * pow(spacing2, 2) * value0)
         / ((spacing0 - spacing1) * (spacing0 - spacing2) * (spacing1 - spacing2));
}
inline BoutReal neumann_o3(BoutReal spacing0, BoutReal value0, BoutReal spacing1,
                           BoutReal value1, BoutReal spacing2, BoutReal value2) {
  return (2 * spacing0 * spacing1 * value2 - 2 * spacing0 * spacing2 * value1
          + pow(spacing1, 2) * spacing2 * value0 - pow(spacing1, 2) * value2
          - spacing1 * pow(spacing2, 2) * value0 + pow(spacing2, 2) * value1)
         / ((spacing1 - spacing2) * (2 * spacing0 - spacing1 - spacing2));
}
} // namespace parallel_stencil

class BoundaryRegionPar : public BoundaryRegionBase {

  struct RealPoint {
    BoutReal s_x;
    BoutReal s_y;
    BoutReal s_z;
  };

  struct Indices {
    // Indices of the boundary point
    Ind3D index;
    // Intersection with boundary in index space
    RealPoint intersection;
    // Distance to intersection
    BoutReal length;
    // Angle between field line and boundary
    // BoutReal angle;
    // How many points we can go in the opposite direction
    signed char valid;
  };

  using IndicesVec = std::vector<Indices>;
  using IndicesIter = IndicesVec::iterator;

  /// Vector of points in the boundary
  IndicesVec bndry_points;
  /// Current position in the boundary points
  IndicesIter bndry_position;

public:
  BoundaryRegionPar(const std::string& name, int dir, Mesh* passmesh)
      : BoundaryRegionBase(name, passmesh), dir(dir) {
    ASSERT0(std::abs(dir) == 1);
    BoundaryRegionBase::isParallel = true;
  }
  BoundaryRegionPar(const std::string& name, BndryLoc loc, int dir, Mesh* passmesh)
      : BoundaryRegionBase(name, loc, passmesh), dir(dir) {
    BoundaryRegionBase::isParallel = true;
    ASSERT0(std::abs(dir) == 1);
  }

  /// Add a point to the boundary
  void add_point(Ind3D ind, BoutReal x, BoutReal y, BoutReal z, BoutReal length,
                 char valid) {
    bndry_points.push_back({ind, {x, y, z}, length, valid});
  }
  void add_point(int ix, int iy, int iz, BoutReal x, BoutReal y, BoutReal z,
                 BoutReal length, char valid) {
    bndry_points.push_back({xyz2ind(ix, iy, iz, localmesh), {x, y, z}, length, valid});
  }

  // final, so they can be inlined
  void first() final { bndry_position = begin(bndry_points); }
  void next() final { ++bndry_position; }
  bool isDone() final { return (bndry_position == end(bndry_points)); }

  // getter
  Ind3D ind() const { return bndry_position->index; }
  BoutReal s_x() const { return bndry_position->intersection.s_x; }
  BoutReal s_y() const { return bndry_position->intersection.s_y; }
  BoutReal s_z() const { return bndry_position->intersection.s_z; }
  BoutReal length() const { return bndry_position->length; }
  char valid() const { return bndry_position->valid; }

  // setter
  void setValid(char val) { bndry_position->valid = val; }

  bool contains(const BoundaryRegionPar& bndry) const {
    return std::binary_search(
        begin(bndry_points), end(bndry_points), *bndry.bndry_position,
        [](const Indices& i1, const Indices& i2) { return i1.index < i2.index; });
  }

  // extrapolate a given point to the boundary
  BoutReal extrapolate_o1(const Field3D& f) const { return f[ind()]; }
  BoutReal extrapolate_o2(const Field3D& f) const {
    ASSERT3(valid() >= 0);
    if (valid() < 1) {
      return extrapolate_o1(f);
    }
    return f[ind()] * (1 + length()) - f.ynext(-dir)[ind().yp(-dir)] * length();
  }

  // dirichlet boundary code
  void dirichlet_o1(Field3D& f, BoutReal value) const {
    f.ynext(dir)[ind().yp(dir)] = value;
  }

  void dirichlet_o2(Field3D& f, BoutReal value) const {
    if (length() < small_value) {
      return dirichlet_o1(f, value);
    }
    ynext(f) = parallel_stencil::dirichlet_o2(1, f[ind()], 1 - length(), value);
    // ynext(f) = f[ind()] * (1 + 1/length()) + value / length();
  }

  void dirichlet_o3(Field3D& f, BoutReal value) const {
    ASSERT3(valid() >= 0);
    if (valid() < 1) {
      return dirichlet_o2(f, value);
    }
    if (length() < small_value) {
      ynext(f) = parallel_stencil::dirichlet_o2(2, yprev(f), 1 - length(), value);
    } else {
      ynext(f) =
          parallel_stencil::dirichlet_o3(2, yprev(f), 1, f[ind()], 1 - length(), value);
    }
  }

  // NB: value needs to be scaled by dy
  // neumann_o1 is actually o2 if we would use an appropriate one-sided stencil.
  // But in general we do not, and thus for normal C2 stencils, this is 1st order.
  void neumann_o1(Field3D& f, BoutReal value) const { ynext(f) = f[ind()] + value; }

  // NB: value needs to be scaled by dy
  void neumann_o2(Field3D& f, BoutReal value) const {
    ASSERT3(valid() >= 0);
    if (valid() < 1) {
      return neumann_o1(f, value);
    }
    ynext(f) = yprev(f) + 2 * value;
  }

  // NB: value needs to be scaled by dy
  void neumann_o3(Field3D& f, BoutReal value) const {
    ASSERT3(valid() >= 0);
    if (valid() < 1) {
      return neumann_o1(f, value);
    }
    ynext(f) =
        parallel_stencil::neumann_o3(1 - length(), value, 1, f[ind()], 2, yprev(f));
  }

  const int dir;

private:
  constexpr static BoutReal small_value = 1e-2;

  // BoutReal get(const Field3D& f, int off)
  const BoutReal& ynext(const Field3D& f) const { return f.ynext(dir)[ind().yp(dir)]; }
  BoutReal& ynext(Field3D& f) const { return f.ynext(dir)[ind().yp(dir)]; }
  const BoutReal& yprev(const Field3D& f) const { return f.ynext(-dir)[ind().yp(-dir)]; }
  BoutReal& yprev(Field3D& f) const { return f.ynext(-dir)[ind().yp(-dir)]; }
  static Ind3D xyz2ind(int x, int y, int z, Mesh* mesh) {
    const int ny = mesh->LocalNy;
    const int nz = mesh->LocalNz;
    return Ind3D{(x * ny + y) * nz + z, ny, nz};
  }
};

#endif //  __PAR_BNDRY_H__
