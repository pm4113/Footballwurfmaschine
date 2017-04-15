CC = gcc -shared -I/usr/include/python2.7/ -lpython2.7 -o
LIB = -lmraa
OBJS = CModule.o 
cmod:$(OBJS)
	$(CC) CModule.so $(LIB) CModule.c

clean:
	rm -f CModule.o CModule.so .CModule.c.un~ CModule.c~ .Makefile.swp
	touch CModule.c
