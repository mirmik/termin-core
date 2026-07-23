#ifndef TERMIN_DISPATCH_API_H
#define TERMIN_DISPATCH_API_H

#ifdef _WIN32
    #ifdef TERMIN_DISPATCH_EXPORTS
        #define TERMIN_DISPATCH_API __declspec(dllexport)
    #else
        #define TERMIN_DISPATCH_API __declspec(dllimport)
    #endif
#else
    #define TERMIN_DISPATCH_API
#endif

#endif
