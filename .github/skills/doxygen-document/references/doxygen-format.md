# Doxygen Format Quick Reference

Source: https://www.doxygen.nl/manual/docblocks.html

---

## C — File Header (required for global symbols)

```c
/**
 * @file filename.h
 * @brief One-line description of the file.
 *
 * Detailed description of the file contents and purpose.
 */
```

---

## C — Function / Method

```c
/**
 * @brief Brief one-line description.
 *
 * Detailed description (optional, after blank line).
 *
 * @param[in]  input_val   Description of input parameter.
 * @param[out] result      Description of output parameter.
 * @param[in,out] buffer   In/out parameter.
 * @return Description of return value. Omit if void.
 * @note  Optional usage note.
 * @warning Optional warning.
 * @see OtherFunction()
 */
int my_function(int input_val, int *result, char *buffer);
```

---

## C — Struct / Union

```c
/**
 * @brief Brief description of the struct.
 *
 * Detailed description.
 */
typedef struct {
    int field_a;    /**< Brief description of field_a. */
    float field_b;  /**< Brief description of field_b. */
} MyStruct;
```

---

## C — Enum

```c
/**
 * @brief Brief description of the enum.
 */
typedef enum {
    STATE_IDLE = 0,   /**< Device is idle. */
    STATE_RUNNING,    /**< Device is running. */
    STATE_ERROR       /**< An error occurred. */
} DeviceState;
```

---

## C — Macro

```c
/** @def MAX_BUFFER_SIZE
 *  @brief Maximum size of the buffer in bytes.
 */
#define MAX_BUFFER_SIZE 1024
```

---

## Python — Module Header

```python
## @package module_name
#  @brief Brief description of the module.
#
#  Detailed description of the module.
```

---

## Python — Class

```python
## @brief Brief description of the class.
#
#  Detailed description.
class MyClass:
    ## @var my_var
    #  Description of class variable.
    my_var = 0
```

---

## Python — Function / Method

```python
## @brief Brief one-line description.
#
#  Detailed description (optional).
#
#  @param self    The object pointer (for methods).
#  @param param1  Description of param1.
#  @param param2  Description of param2.
#  @return Description of return value. Omit if None.
#  @note  Optional note.
#  @warning Optional warning.
def my_function(self, param1, param2):
    pass
```

---

## Key Doxyfile Settings for Python + C Projects

| Setting | Recommended Value | Reason |
|---------|------------------|--------|
| `OPTIMIZE_OUTPUT_JAVA` | `YES` | Correct output for Python (Java-like structure) |
| `EXTRACT_ALL` | `YES` | Document even entities without docstrings |
| `FILE_PATTERNS` | `*.py *.h *.c` | Match all relevant source file types |
| `RECURSIVE` | `YES` | Scan subdirectories |
| `INPUT` | list of source dirs | Point to actual source roots |
| `PYTHON_DOCSTRING` | `NO` | Forces `##`-style parsing over `"""` style |

---

## Common Special Commands

| Command | Usage |
|---------|-------|
| `@brief` | One-line summary |
| `@param[in/out/in,out] name desc` | Parameter documentation |
| `@return desc` | Return value |
| `@note desc` | Usage note |
| `@warning desc` | Warning |
| `@see symbol` | Cross-reference |
| `@deprecated desc` | Mark as deprecated |
| `@throws ExceptionType desc` | Exception documentation |
| `@tparam T desc` | Template parameter (C++) |
| `@file` | File-level documentation marker |
| `@package` | Python module marker |
| `@var` | Variable documentation marker |
| `@def` | Macro documentation marker |
