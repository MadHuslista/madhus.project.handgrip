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


template <typename T>
class FIFObuf {
private:
    int _head = 0;
    int _tail = 0;
    size_t _bufferSize;
    T* _buffer;

public:
    FIFObuf(size_t bufferSize)
    {
        _head = 0;
        _tail = 0;
        _bufferSize = bufferSize + 1;
        _buffer = new T[_bufferSize];
    }

    ~FIFObuf()
    {
        if (_buffer != nullptr) {
            delete[] _buffer;
        }
    }

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

    bool is_empty()
    {
        return _head == _tail;
    }

    T at(unsigned int index)
    {
        if (index >= size()) {
            return T();
        }
        size_t currentInd = (_tail + index) % _bufferSize;
        return _buffer[currentInd];
    }

    size_t size()
    {
        return (_bufferSize + _head - _tail) % _bufferSize;
    }

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
