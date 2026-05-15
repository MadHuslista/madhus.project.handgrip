/**
 ******************************************************************************
 * @file    fifo_buffer.h
 * @author  Nicolas Schiappacasse <nicolaschiappacase@gmail.com>
 * @date    03/2026
 * @brief   Adaptation of the FIFO buffer from https://github.com/pervu/FIFObuf
 *
 ******************************************************************************
 */
#ifndef _INC_FIFO_BUFFER_H_
#define _INC_FIFO_BUFFER_H_

/** @addtogroup HandGrip
 * @{
 */
/** @addtogroup Application
 * @{
 */
/** @addtogroup Config
 * @{
 */

#include <Arduino.h>

/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_Definitions                                            */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_Types                                                  */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/**
 * @brief Fixed-size circular FIFO buffer.
 * @tparam T Element type stored in the FIFO.
 */
template <typename T>
class FIFObuf {
private:
    int _head = 0;
    int _tail = 0;
    size_t _bufferSize;
    T* _buffer;

public:
    /**
     * @brief Construct a FIFO with the requested usable capacity.
     * @param[in] bufferSize Maximum number of elements to hold.
     */
    FIFObuf(size_t bufferSize)
    {
        _head = 0;
        _tail = 0;
        _bufferSize = bufferSize + 1;
        _buffer = new T[_bufferSize];
    }

    /**
     * @brief Destroy the FIFO and release owned storage.
     */
    ~FIFObuf()
    {
        if (_buffer != nullptr) {
            delete[] _buffer;
        }
    }

    /**
     * @brief Push one element into the FIFO.
     * @param[in] data Element to enqueue.
     * @return true if the element was enqueued; false when the buffer is full.
     */
    bool push(T data)
    {
        size_t newHead = (_head + 1) % _bufferSize;
        if ((int)newHead == _tail) {
            return false; // Buffer overflow
        } else {
            _buffer[_head] = data;
            _head = newHead;
            return true;
        }
    }

    /**
     * @brief Pop one element from the FIFO.
     * @return Front element when available; default-constructed value when empty.
     */
    T pop()
    {
        if (_head == _tail) {
            return T(); // Buffer empty
        } else {
            T data = _buffer[_tail];
            _tail = (_tail + 1) % _bufferSize;
            return data;
        }
    }

    /**
     * @brief Check whether the FIFO has no elements.
     * @return true when empty; false otherwise.
     */
    bool is_empty()
    {
        return _head == _tail;
    }

    /**
     * @brief Read an element by logical FIFO index without removing it.
     * @param[in] index Zero-based index from the current FIFO tail.
     * @return Element at the requested index; default-constructed value if out of range.
     */
    T at(unsigned int index)
    {
        if (index >= size()) {
            return T();
        }
        size_t currentInd = (_tail + index) % _bufferSize;
        return _buffer[currentInd];
    }

    /**
     * @brief Get the number of currently stored elements.
     * @return Element count currently in the FIFO.
     */
    size_t size()
    {
        return (_bufferSize + _head - _tail) % _bufferSize;
    }

    /**
     * @brief Remove all elements from the FIFO.
     */
    void clear()
    {
        _head = 0;
        _tail = 0;
    }

};


/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_Data                                                  */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_API                                                    */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/** @} */
/*----------------------------------------------------------------------------*/
/** @addtogroup PUBLIC_WEAK                                                   */
/**@{                                                                         */
/*----------------------------------------------------------------------------*/

/*----------------------------------------------------------------------------*/
/** @} */
/*--->> END: PUBLIC API <<----------------------------------------------------*/

/** @} */
/** @} */
/** @} */

#endif   //  _INC_FIFO_BUFFER_H_
