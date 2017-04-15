#include <python2.7/Python.h>
#include "mraa.h"

#define baud 115200

static mraa_uart_context uart;
static interrupt = 0;


static PyObject* py_InterruptUartReadOn(PyObject* self, PyObject* args){
	interrupt = 1;
	return Py_BuildValue("i", 1);
}


static PyObject* py_InterruptUartReadOff(PyObject* self, PyObject* args){
	interrupt = 0;
	return Py_BuildValue("i", 0);
}


static PyObject* py_InterruptUartReadStatus(PyObject* self, PyObject* args){
	return Py_BuildValue("i", interrupt);
}


static PyObject* py_UartSend(PyObject* self, PyObject* args){
	int numItems, i;
	PyObject *data;
	int *data_i;
	char *data_c;
	interrupt = 0;

	if (!PyArg_ParseTuple(args, "O", &data)){
		return NULL;
		printf("Uart Data send Fail");
	}

	numItems = PyTuple_Size(data);
	data_i = malloc(numItems*4);
	data_c = malloc(numItems*4);

	for (i=0; i<numItems; i++){
		data_i[i] = (int) PyInt_AsLong(PyTuple_GetItem(data, i));
		data_c[i] = (char) data_i[i];
	}

	mraa_uart_write(uart, data_c, numItems);
	mraa_uart_flush(uart);
	free(data_i);
	free(data_c);
	return Py_BuildValue("c", 1);
}


static PyObject* py_UartReceive(PyObject* self, PyObject* args){
	char *NoData = "NODATA";
	if (interrupt == 0){
		unsigned char data[1]= {0};
		char *data_storage;
		data_storage = malloc(100); 
		int i = 0;
		int e = 0;	
//		printf("1");
		if (mraa_uart_data_available(uart, 1)){
			while (1){
				mraa_uart_read(uart, data, 1);
				data_storage[i] = data[0];
				i++;
				if (mraa_uart_data_available(uart, 1) == 0){	
					break;
					free(data_storage);
				}
			}			
			return Py_BuildValue("s#", data_storage, i);
		}
		else
			free(data_storage); 
			return Py_BuildValue("s",NoData);
	}
	else{
		return Py_BuildValue("s",NoData);
	}
}

static PyMethodDef CModule_methods[] = {
	{"UartSend", py_UartSend,  METH_VARARGS},
	{"UartReceive", py_UartReceive, METH_VARARGS},
	{"InterruptUartReadOn", py_InterruptUartReadOn, METH_VARARGS},
	{"InterruptUartReadOff", py_InterruptUartReadOff, METH_VARARGS},
	{"InterruptUartReadStatus", py_InterruptUartReadStatus, METH_VARARGS},
	{NULL, NULL}
};

void initCModule(){
	uart = mraa_uart_init(0);
	mraa_uart_set_baudrate(uart, baud);
	mraa_uart_set_non_blocking(uart, 0);
	(void) Py_InitModule("CModule", CModule_methods);
}
