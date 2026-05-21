/// @file tc_vec3.h
/// @brief 3D вектор и операции над ним

#ifndef TC_VEC3_H
#define TC_VEC3_H

#include <tcbase/tc_types.h>
#include <math.h>

// C/C++ compatible struct initialization
#ifdef __cplusplus
    #define TC_VEC3(x, y, z) tc_vec3{x, y, z}
#else
    #define TC_VEC3(x, y, z) (tc_vec3){x, y, z}
#endif

#ifdef __cplusplus
extern "C" {
#endif

/// @name Конструкторы
/// @{

/// Создаёт вектор с заданными компонентами
/// @param x Компонента X
/// @param y Компонента Y
/// @param z Компонента Z
/// @return Новый вектор (x, y, z)
static inline tc_vec3 tc_vec3_new(double x, double y, double z) {
    return TC_VEC3(x, y, z);
}

/// Создаёт нулевой вектор (0, 0, 0)
static inline tc_vec3 tc_vec3_zero(void) {
    return TC_VEC3(0, 0, 0);
}

/// Создаёт единичный вектор (1, 1, 1)
static inline tc_vec3 tc_vec3_one(void) {
    return TC_VEC3(1, 1, 1);
}

/// Единичный вектор оси X (1, 0, 0)
static inline tc_vec3 tc_vec3_unit_x(void) { return TC_VEC3(1, 0, 0); }

/// Единичный вектор оси Y (0, 1, 0)
static inline tc_vec3 tc_vec3_unit_y(void) { return TC_VEC3(0, 1, 0); }

/// Единичный вектор оси Z (0, 0, 1)
static inline tc_vec3 tc_vec3_unit_z(void) { return TC_VEC3(0, 0, 1); }

/// @}

/// @name Арифметика
/// @{

/// Покомпонентное сложение векторов
/// @param a Первый вектор
/// @param b Второй вектор
/// @return a + b
static inline tc_vec3 tc_vec3_add(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x + b.x, a.y + b.y, a.z + b.z);
}

/// Покомпонентное вычитание векторов
/// @param a Первый вектор
/// @param b Второй вектор
/// @return a - b
static inline tc_vec3 tc_vec3_sub(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x - b.x, a.y - b.y, a.z - b.z);
}

/// Покомпонентное умножение векторов
/// @param a Первый вектор
/// @param b Второй вектор
/// @return (a.x*b.x, a.y*b.y, a.z*b.z)
static inline tc_vec3 tc_vec3_mul(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x * b.x, a.y * b.y, a.z * b.z);
}

/// Покомпонентное деление векторов
/// @param a Первый вектор
/// @param b Второй вектор (компоненты не должны быть нулевыми)
/// @return (a.x/b.x, a.y/b.y, a.z/b.z)
static inline tc_vec3 tc_vec3_div(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(a.x / b.x, a.y / b.y, a.z / b.z);
}

/// Умножение вектора на скаляр
/// @param v Вектор
/// @param s Скаляр
/// @return v * s
static inline tc_vec3 tc_vec3_scale(tc_vec3 v, double s) {
    return TC_VEC3(v.x * s, v.y * s, v.z * s);
}

/// Инвертирует вектор
/// @param v Вектор
/// @return -v
static inline tc_vec3 tc_vec3_neg(tc_vec3 v) {
    return TC_VEC3(-v.x, -v.y, -v.z);
}

/// @}

/// @name Произведения
/// @{

/// Скалярное произведение
/// @param a Первый вектор
/// @param b Второй вектор
/// @return a · b
static inline double tc_vec3_dot(tc_vec3 a, tc_vec3 b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

/// Векторное произведение
/// @param a Первый вектор
/// @param b Второй вектор
/// @return a × b
static inline tc_vec3 tc_vec3_cross(tc_vec3 a, tc_vec3 b) {
    return TC_VEC3(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x
    );
}

/// @}

/// @name Длина и нормализация
/// @{

/// Квадрат длины вектора
/// @param v Вектор
/// @return |v|²
static inline double tc_vec3_length_sq(tc_vec3 v) {
    return v.x * v.x + v.y * v.y + v.z * v.z;
}

/// Длина вектора
/// @param v Вектор
/// @return |v|
static inline double tc_vec3_length(tc_vec3 v) {
    return sqrt(tc_vec3_length_sq(v));
}

/// Нормализует вектор
/// @param v Вектор
/// @return Единичный вектор того же направления, или (0,0,0) если |v| ≈ 0
static inline tc_vec3 tc_vec3_normalize(tc_vec3 v) {
    double len = tc_vec3_length(v);
    if (len < 1e-12) return tc_vec3_zero();
    return tc_vec3_scale(v, 1.0 / len);
}

/// Расстояние между двумя точками
/// @param a Первая точка
/// @param b Вторая точка
/// @return |a - b|
static inline double tc_vec3_distance(tc_vec3 a, tc_vec3 b) {
    return tc_vec3_length(tc_vec3_sub(a, b));
}

/// @}

/// @name Интерполяция
/// @{

/// Линейная интерполяция между векторами
/// @param a Начальный вектор (t=0)
/// @param b Конечный вектор (t=1)
/// @param t Параметр интерполяции [0, 1]
/// @return a + (b - a) * t
static inline tc_vec3 tc_vec3_lerp(tc_vec3 a, tc_vec3 b, double t) {
    return TC_VEC3(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        a.z + (b.z - a.z) * t
    );
}

/// @}

/// @name Сравнение
/// @{

/// Точное сравнение векторов
/// @param a Первый вектор
/// @param b Второй вектор
/// @return true если все компоненты равны
static inline bool tc_vec3_eq(tc_vec3 a, tc_vec3 b) {
    return a.x == b.x && a.y == b.y && a.z == b.z;
}

/// Приближённое сравнение векторов
/// @param a Первый вектор
/// @param b Второй вектор
/// @param eps Допустимая погрешность
/// @return true если |a.x - b.x| < eps для всех компонент
static inline bool tc_vec3_near(tc_vec3 a, tc_vec3 b, double eps) {
    return fabs(a.x - b.x) < eps && fabs(a.y - b.y) < eps && fabs(a.z - b.z) < eps;
}

/// @}

#ifdef __cplusplus
}
#endif

#endif // TC_VEC3_H
