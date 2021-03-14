//============================================================================
// Name        : DisplayNixie.cpp
// Author      : GRA&AFCH @ Leon Shaner; Tony Gillett
// Version     : v2.3.2
// Copyright   : Free
// Description : Display time on shields NCS314 v2.x or NCS312
//============================================================================

#define _VERSION "2.3.2 SHANER GILLETT"

#include <stdio.h>
#include <stdlib.h>
#include <getopt.h>
#include <iostream>
#include <wiringPi.h>
#include <wiringPiSPI.h>
#include <ctime>
#include <string.h>
#include <wiringPiI2C.h>
#include <softTone.h>
#include <softPwm.h>
#include <signal.h>

using namespace std;
#define R5222_PIN 22
bool HV5222;
#define LEpin 3
#define UP_BUTTON_PIN 1
#define DOWN_BUTTON_PIN 4
#define MODE_BUTTON_PIN 5
#define BUZZER_PIN 0
#define I2CAdress 0x68
#define I2CFlush 0

#define DEBOUNCE_DELAY 150
#define TOTAL_DELAY 10
#define CATHODE_PROTECTION_DELAY_SHORT 100
#define CATHODE_PROTECTION_DELAY_LONG 10000
#define CATHODE_PROTECTION_LONG_TIME_1 "020000" // Must align to an hour
#define CATHODE_PROTECTION_LONG_TIME_2 "040000" // Must align to an hour

#define SECOND_REGISTER 0x0
#define MINUTE_REGISTER 0x1
#define HOUR_REGISTER 0x2
#define WEEK_REGISTER 0x3
#define DAY_REGISTER 0x4
#define MONTH_REGISTER 0x5
#define YEAR_REGISTER 0x6

#define RED_LIGHT_PIN 28
#define GREEN_LIGHT_PIN 27
#define BLUE_LIGHT_PIN 29
#define MAX_POWER_EXTENT 100
#define MAX_POWER 100
#define INIT_CYCLE_FREQ 400
#define INIT_CYCLE_BUMP 50

#define UPPER_DOTS_MASK 0x80000000
#define LOWER_DOTS_MASK 0x40000000

#define LEFT_REPR_START 5
#define LEFT_BUFFER_START 0
#define RIGHT_REPR_START 2
#define RIGHT_BUFFER_START 4

#define ASCII_ZERO 48
#define ASCII_NINE 57

#define DISPLAY_POS_M2 3
#define DISPLAY_POS_S1 4
#define DISPLAY_POS_S2 5

#define TIME_STR_LENGTH 6

uint16_t SymbolArray[10] = {1, 2, 4, 8, 16, 32, 64, 128, 256, 512};

int fileDesc;

int redLight = 0;
int greenLight = 0;
int blueLight = 0;
int lightCycle = 0;
bool dotState = 0;
int rotator = 0;
int maxLEDBrightness = MAX_POWER;
unsigned long fireworksCyclePeriod = INIT_CYCLE_FREQ;
char _lastStringDisplayed[8];
bool continueRunningClock = true;

string cathodeProtectionLongTime[2] = {CATHODE_PROTECTION_LONG_TIME_1, CATHODE_PROTECTION_LONG_TIME_2};
string turnClockOnTime;
string turnClockOffTime;

bool clockIsSwitchedOn = true;

// Set initial fireworks mode true=on; false=off
bool doFireworks = false;

// Set default clock mode
// NOTE:  true means rely on system to keep time (e.g. NTP assisted for accuracy).
bool useSystemRTC = true;

// Set the hour mode
// Set use12hour = true for hours 0-12 and 1-11 (e.g. a.m./p.m. implied)
// Set use12hour = false for hours 0-23
bool use12hour = true;
bool isStartup = true;
bool doCathodeProtection = true;

int bcdToDec(int val) {
	return ((val / 16  * 10) + (val % 16));
}

int decToBcd(int val) {
	return ((val / 10  * 16) + (val % 10));
}

tm addHourToDate(tm date) {
	date.tm_hour += 1;
	mktime(&date);
	return date;
}

tm addMinuteToDate(tm date) {
	date.tm_min += 1;
	mktime(&date);
	return date;
}

tm getRTCDate() {
	wiringPiI2CWrite(fileDesc, I2CFlush);
	tm date;
	date.tm_sec =  bcdToDec(wiringPiI2CReadReg8(fileDesc, SECOND_REGISTER));
	date.tm_min =  bcdToDec(wiringPiI2CReadReg8(fileDesc, MINUTE_REGISTER));
	if (use12hour)
	{
		date.tm_hour = bcdToDec(wiringPiI2CReadReg8(fileDesc, HOUR_REGISTER));
		if (date.tm_hour > 12)
			date.tm_hour -= 12;
	}
	else
		date.tm_hour = bcdToDec(wiringPiI2CReadReg8(fileDesc, HOUR_REGISTER));
	date.tm_wday = bcdToDec(wiringPiI2CReadReg8(fileDesc, WEEK_REGISTER));
	date.tm_mday = bcdToDec(wiringPiI2CReadReg8(fileDesc, DAY_REGISTER));
	date.tm_mon =  bcdToDec(wiringPiI2CReadReg8(fileDesc, MONTH_REGISTER));
	date.tm_year = bcdToDec(wiringPiI2CReadReg8(fileDesc, YEAR_REGISTER));
	date.tm_isdst = 0;
	return date;
}

void updateRTCHour(tm date) {
	wiringPiI2CWrite(fileDesc, I2CFlush);
	wiringPiI2CWriteReg8(fileDesc,HOUR_REGISTER,decToBcd(date.tm_hour));
	wiringPiI2CWrite(fileDesc, I2CFlush);
}

void updateRTCMinute(tm date) {
	wiringPiI2CWrite(fileDesc, I2CFlush);
	wiringPiI2CWriteReg8(fileDesc,MINUTE_REGISTER,decToBcd(date.tm_min));
	wiringPiI2CWriteReg8(fileDesc,HOUR_REGISTER,decToBcd(date.tm_hour));
	wiringPiI2CWrite(fileDesc, I2CFlush);
}
void resetRTCSecond() {
	wiringPiI2CWrite(fileDesc, I2CFlush);
	wiringPiI2CWriteReg8(fileDesc,SECOND_REGISTER, 0);
	wiringPiI2CWrite(fileDesc, I2CFlush);
}

void writeRTCDate(tm date) {
	wiringPiI2CWrite(fileDesc, I2CFlush);
	wiringPiI2CWriteReg8(fileDesc,SECOND_REGISTER,decToBcd(date.tm_sec));
	wiringPiI2CWriteReg8(fileDesc,MINUTE_REGISTER,decToBcd(date.tm_min));
	wiringPiI2CWriteReg8(fileDesc,HOUR_REGISTER,decToBcd(date.tm_hour));
	wiringPiI2CWriteReg8(fileDesc,WEEK_REGISTER,decToBcd(date.tm_wday));
	wiringPiI2CWriteReg8(fileDesc,DAY_REGISTER,decToBcd(date.tm_mday));
	wiringPiI2CWriteReg8(fileDesc,MONTH_REGISTER,decToBcd(date.tm_mon));
	wiringPiI2CWriteReg8(fileDesc,YEAR_REGISTER,decToBcd(date.tm_year));
	wiringPiI2CWrite(fileDesc, I2CFlush);
}

void initPin(int pin) {
	pinMode(pin, INPUT);
	pullUpDnControl(pin, PUD_UP);
}

void resetFireWorks() {
    printf("in resetFireWorks\n");
	redLight = 0;
	greenLight = 0;
	blueLight = 0; 
	softPwmWrite(RED_LIGHT_PIN, redLight);
	softPwmWrite(GREEN_LIGHT_PIN, greenLight);
	softPwmWrite(BLUE_LIGHT_PIN, blueLight);
}

void initFireWorks() {
    printf("in initFireWorks\n");
	redLight = maxLEDBrightness;
	greenLight = 0;
	blueLight = 0; 
	softPwmWrite(RED_LIGHT_PIN, redLight);
	softPwmWrite(GREEN_LIGHT_PIN, greenLight);
	softPwmWrite(BLUE_LIGHT_PIN, blueLight);
}

void funcMode(void) {
	static unsigned long modeTime = 0;
	if ((millis() - modeTime) > DEBOUNCE_DELAY) {
		puts("MODE button was pressed.");
        // Mode Switch toggles Fireworks on/off
		doFireworks = !doFireworks;
		if (!doFireworks)
			resetFireWorks();
		else
			initFireWorks();
		modeTime = millis();
	}
}

void funcUp(void) {
	static unsigned long buttonTime = 0;
	if ((millis() - buttonTime) > DEBOUNCE_DELAY) {
        // Up button speeds up Fireworks
		fireworksCyclePeriod = (fireworksCyclePeriod - INIT_CYCLE_BUMP);
		if (fireworksCyclePeriod < 0) {
			fireworksCyclePeriod = 0;
		}
		printf("Up button was pressed. Frequency=%lu\n", fireworksCyclePeriod);
		buttonTime = millis();
	}
}

void funcDown(void) {
	static unsigned long buttonTime = 0;
	if ((millis() - buttonTime) > DEBOUNCE_DELAY) {
        // Down button slows down Fireworks
		fireworksCyclePeriod = (fireworksCyclePeriod - INIT_CYCLE_BUMP);
		printf("Down button was pressed. Frequency=%lu\n", fireworksCyclePeriod);
	}
	buttonTime = millis();
}

uint32_t get32Rep(char * _stringToDisplay, int start) {
	uint32_t var32 = 0;

	var32= (SymbolArray[_stringToDisplay[start] - 0x30]) << 20;
	var32|=(SymbolArray[_stringToDisplay[start - 1] - 0x30]) << 10;
	var32|=(SymbolArray[_stringToDisplay[start - 2] - 0x30]);
	return var32;
}

void fillBuffer(uint32_t var32, unsigned char * buffer, int start) {
	buffer[start] = var32 >> 24;
	buffer[start + 1] = var32 >> 16;
	buffer[start + 2] = var32 >> 8;
	buffer[start + 3] = var32;
}

void dotBlink()
{
    dotState = !dotState;
}

void rotateFireWorks() {
    printf("in rotateFireWorks\n");
    
	int fireworks[] = {0,0,1,
					  -1,0,0,
			           0,1,0,
					   0,0,-1,
					   1,0,0,
					   0,-1,0
	};
    
	redLight += fireworks[rotator * 3];
	greenLight += fireworks[rotator * 3 + 1];
	blueLight += fireworks[rotator * 3 + 2];
    
	softPwmWrite(RED_LIGHT_PIN, redLight);
	softPwmWrite(GREEN_LIGHT_PIN, greenLight);
	softPwmWrite(BLUE_LIGHT_PIN, blueLight);
    
	lightCycle += 1;
	if (lightCycle == maxLEDBrightness) {
		rotator = rotator + 1;
		lightCycle  = 0;
	}
	if (rotator > 5) {
        rotator = 0;
    }
}

uint32_t addBlinkTo32Rep(uint32_t var) {
	if (dotState)
	{
		var &=~LOWER_DOTS_MASK;
		var &=~UPPER_DOTS_MASK;
	}
	else
	{
		var |=LOWER_DOTS_MASK;
		var |=UPPER_DOTS_MASK;
	}
	return var;
}

void switchOnClock()
{
    if (doFireworks) {
        initFireWorks();
    }
    clockIsSwitchedOn = true;
}

void switchOffClock()
{
    clockIsSwitchedOn = false;
    digitalWrite(LEpin, LOW);
    resetFireWorks();
}

// Interrupt handler to turn off Nixie upon SIGINT(2), SIGQUIT(3), SIGTERM(15), but not SIGKILL(9)
void signal_handler (int sig_received)
{
	printf("Received Signal %d; Exiting.\n", sig_received);
	//exit(sig_received);
    continueRunningClock = false;
}

uint64_t reverseBit(uint64_t num);

void displayOnTubes(char* _stringToDisplayOnTubes)
{
    unsigned char buff[8];

    uint32_t var32 = get32Rep(_stringToDisplayOnTubes, LEFT_REPR_START);
    var32 = addBlinkTo32Rep(var32);
    fillBuffer(var32, buff , LEFT_BUFFER_START);

    var32 = get32Rep(_stringToDisplayOnTubes, RIGHT_REPR_START);
    var32 = addBlinkTo32Rep(var32);
    fillBuffer(var32, buff , RIGHT_BUFFER_START);

    digitalWrite(LEpin, LOW);

    if (HV5222)
    {
        uint64_t reverseBuffValue;
        reverseBuffValue = reverseBit(*(uint64_t*)buff);
        buff[4] = reverseBuffValue;
        buff[5] = reverseBuffValue >> 8;
        buff[6] = reverseBuffValue >> 16;
        buff[7] = reverseBuffValue >> 24;
        buff[0] = reverseBuffValue >> 32;
        buff[1] = reverseBuffValue >> 40;
        buff[2] = reverseBuffValue >> 48;
        buff[3] = reverseBuffValue >> 56;
    }

    wiringPiSPIDataRW(0, buff, 8);
    digitalWrite(LEpin, HIGH);
    strcpy(_lastStringDisplayed, _stringToDisplayOnTubes);
}


/* Flag set by ‘--verbose’. */
static int use12hourFlag;

int main(int argc, char* argv[]) {

    //int c;
    
    while (1)
    {
        static struct option long_options[] =
        {
            /* These options set a flag. */
            {"12hour",            no_argument,       &use12hourFlag, 1},
            {"24hour",            no_argument,       &use12hourFlag, 0},
            /* These options don’t set a flag.
               We distinguish them by their indices. */
            {"no-sysclock",       no_argument,       0, 'c'},
            {"fireworks",         required_argument, 0, 'f'},
            {"no-protect",        no_argument,       0, 'n'},
            {"extended-protect1", required_argument, 0, 'p'},
            {"extended-protect2", required_argument, 0, 'q'},
            {"turn-on-at",        required_argument, 0, 'o'},
            {"turn-off-at",       required_argument, 0, 's'},
            {"brightness",        required_argument, 0, 'b'},
            {0, 0, 0, 0}
        };
        
        /* getopt_long stores the option index here. */
        int option_index = 0;

        int c = getopt_long (argc, argv, "cf:np:q:o:s:b:", long_options, &option_index);

        /* Detect the end of the options. */
        if (c == -1) {
            break;
        }

        // Basic command line args handling. Note that code is not robust - no checks on the format/validity of user inputs.
        switch (c)
        {
            case 0:
                /* If this option set a flag, do nothing else now. */
                if (long_options[option_index].flag != 0)
                  break;
                printf ("option %s", long_options[option_index].name);
                if (optarg)
                    printf (" with arg %s", optarg);
                printf ("\n");
                break;
                
            case 'c':
                // Don't use system clock
                useSystemRTC = false;
                break;

            case 'f':
                // do fireworks
                fireworksCyclePeriod = atoi(optarg);
                doFireworks = (fireworksCyclePeriod != 0);
                break;
                
           case 'n':
                // disable cathode protection
                doCathodeProtection = false;
                break;
                
            case 'p':
                cathodeProtectionLongTime[0] = optarg;
                break;
                
            case 'q':
                cathodeProtectionLongTime[1] = optarg;
                break;
                
            case 'o':
                turnClockOnTime = optarg;
                break;
                
            case 's':
                turnClockOffTime = optarg;
                break;
                
            case 'b':
                maxLEDBrightness = atoi(optarg);
                break;

            default:
                printf("aborting");
                abort ();
            }
    }
    
    use12hour = use12hourFlag;

    /* Print any remaining command line arguments (not options). 
    if (optind < argc)
    {
        printf ("non-option ARGV-elements: ");
        while (optind < argc)
          printf ("%s ", argv[optind++]);
        putchar ('\n');
    }
    */
    
	// Setup signal handlers
  	signal(SIGINT, signal_handler);
  	signal(SIGQUIT, signal_handler);
  	signal(SIGTERM, signal_handler);

	printf("Nixie Clock v%s \n\r", _VERSION);

	wiringPiSetup();


    // Tell the user the RTC mode
	if (useSystemRTC)
		puts("Using system RTC (eg. NTP assisted accuracy).");
	else
		puts("Using Nixie embedded RTC (e.g. not NTP assisted).");

    // Tell the user the hour mode
	if (use12hour)
		puts("Using 12-hour display (implied a.m./p.m.).");
	else
		puts("Using 24-hour display.");

    // Tell the user the fireworks mode
	if (doFireworks)
		puts("Fireworks ENABLED at start.");
	else
		puts("Fireworks DISABLED at start.");
        
    // Tell the user the cathode protection mode
	if (doCathodeProtection)
		puts("Cathode poisoning protection ENABLED at start.");
	else
		puts("Cathode poisoning protection DISABLED at start.");
        
    printf("Maximum LED brightness set at %d\n", maxLEDBrightness);
    
    if (turnClockOffTime.length() == TIME_STR_LENGTH) {
        printf("Clock switch off time set to %s\n", turnClockOffTime.c_str());
    }

    if (turnClockOnTime.length() == TIME_STR_LENGTH) {
        printf("Clock switch on time set to %s\n", turnClockOnTime.c_str());
    }

    if (cathodeProtectionLongTime[0].length() == TIME_STR_LENGTH) {
        printf("Long cathode protection will run at %s\n", cathodeProtectionLongTime[0].c_str());
    }
    
    if (cathodeProtectionLongTime[1].length() == TIME_STR_LENGTH) {
        printf("Long cathode protection will run at %s\n", cathodeProtectionLongTime[1].c_str());
    }    

    //printf("just exiting.\n");
    //exit(EXIT_SUCCESS);
    // test stuff end

    // TODO - tell use off/on times if set, cathode protection etc.

    // Further setup...
	initPin(UP_BUTTON_PIN);
	initPin(DOWN_BUTTON_PIN);
	initPin(MODE_BUTTON_PIN);

    // Initial setup for multi-color LED's based on default doFireworks boolean
    softPwmCreate(GREEN_LIGHT_PIN, 0, MAX_POWER_EXTENT);
    softPwmCreate(BLUE_LIGHT_PIN, 0, MAX_POWER_EXTENT);
    softPwmCreate(RED_LIGHT_PIN, 0, MAX_POWER_EXTENT);
	if (doFireworks) {
		initFireWorks();
    }
    else
	{
		resetFireWorks();
	}

    // Mode Switch toggles Fireworks on/off
	wiringPiISR(MODE_BUTTON_PIN, INT_EDGE_RISING, &funcMode);

    // Open the Nixie device
	fileDesc = wiringPiI2CSetup(I2CAdress);

    // Further date setup
	tm date = getRTCDate();
	time_t seconds = time(NULL);
	tm* timeinfo = localtime (&seconds);

    // Tell the user the SPI status
	if (wiringPiSPISetupMode (0, 2000000, 2)) {
		puts("SPI ok");
	}
	else {
		puts("SPI NOT ok");
		return 0;
	}

	pinMode(R5222_PIN, INPUT);
	pullUpDnControl(R5222_PIN, PUD_UP);
	HV5222 = !digitalRead(R5222_PIN);
	if (HV5222) puts("R52222 resistor detected. HV5222 algorithm is used.");

    // Loop forever displaying the time
	long buttonDelay = millis();
    unsigned long lastRotateFireworks = millis();

	do {      
		char _stringToDisplay[8];

        // NOTE:  RTC relies on system to keep time (e.g. NTP assisted for accuracy).
		if (useSystemRTC)
		{
			seconds = time(NULL);
			timeinfo = localtime (&seconds);
			date.tm_mday = timeinfo->tm_mday;
			date.tm_wday = timeinfo->tm_wday;
			date.tm_mon =  timeinfo->tm_mon + 1;
			date.tm_year = timeinfo->tm_year - 100;
			writeRTCDate(*timeinfo);
		}

        // NOTE:  RTC relies on Nixie to keep time (e.g. no NTP).
		date = getRTCDate();

		char* format = (char*) "%H%M%S";
		strftime(_stringToDisplay, 8, format, &date);
        
        if (clockIsSwitchedOn) {
            if (strcmp(_stringToDisplay, turnClockOffTime.c_str()) == 0) {
                printf("Turning off clock at %s\n", _stringToDisplay);
                switchOffClock();
            }
        } else {
                if (strcmp(_stringToDisplay, turnClockOnTime.c_str()) == 0) {
                    printf("Clock switching on at %s\n", _stringToDisplay);
                    switchOnClock();
                }
        }
        
        if (doFireworks && clockIsSwitchedOn)
		{
			// Handle Fireworks speed UP / Down
			if (digitalRead(UP_BUTTON_PIN) == 0 && (millis() - buttonDelay) > DEBOUNCE_DELAY) {
				funcUp();
				initFireWorks();
				buttonDelay = millis();
			}
			if (digitalRead(DOWN_BUTTON_PIN) == 0 && (millis() - buttonDelay) > DEBOUNCE_DELAY) {
				funcDown();
				initFireWorks();
				buttonDelay = millis();
			}
            if (millis() > (lastRotateFireworks + fireworksCyclePeriod)) {
                rotateFireWorks();
                lastRotateFireworks = millis();
            }
		}

		pinMode(LEpin, OUTPUT); // todo: move this to outside of loop, so run one-time only???
		
        // On startup and every ten minutes, invoke short cathode poisoning protection 
        bool isTimeForLongProtection = (strcmp(_stringToDisplay, cathodeProtectionLongTime[0].c_str()) == 0) || (strcmp(_stringToDisplay, cathodeProtectionLongTime[1].c_str()) == 0);
        bool isTimeForShortProtection = ((_stringToDisplay[DISPLAY_POS_S2] == ASCII_ZERO) && (_stringToDisplay[DISPLAY_POS_S1] == ASCII_ZERO) && (_stringToDisplay[DISPLAY_POS_M2] == ASCII_ZERO));
        
        if ( 
          doCathodeProtection && (isStartup || isTimeForShortProtection || isTimeForLongProtection )
          ) 
        {
            // Run cathode poisoning protection 
			
            isStartup = false;
			int doCathodeProtectionLingerTime = CATHODE_PROTECTION_DELAY_SHORT;
			// Run extended version of cathode protection twice daily
            if (isTimeForLongProtection) {
				printf("Do cathode poisoning protection (long version)\n");
				doCathodeProtectionLingerTime = CATHODE_PROTECTION_DELAY_LONG;
			}			
            
            int characterToDisplay = ASCII_ZERO;
            
            for (int cycleIndex = 0; cycleIndex < 10; cycleIndex++) {
                characterToDisplay = ASCII_ZERO + cycleIndex;
                
                for (int stringIndex = 0; stringIndex <= DISPLAY_POS_S2; stringIndex++) {
                    _stringToDisplay[stringIndex] = char(characterToDisplay);
                    
                    characterToDisplay++;
                    if (characterToDisplay > ASCII_NINE) {
                        characterToDisplay = ASCII_ZERO;
                    }
                }
                
                displayOnTubes(_stringToDisplay);
                delay (doCathodeProtectionLingerTime);
            }
            
            if (!clockIsSwitchedOn) {
                switchOffClock();
            }
        }
        
		// Update tubes (only) if time has changed since last update and toggle columns blink (and only if clock is switched on)
        if (clockIsSwitchedOn && (strcmp(_lastStringDisplayed, _stringToDisplay) != 0)) {
            dotBlink();
            displayOnTubes(_stringToDisplay);        
        }
        
        delay (TOTAL_DELAY);
	}
	while (continueRunningClock);
    
    switchOffClock();
    
    printf("end of Main\n");
	return 0;
}

uint64_t reverseBit(uint64_t num)
{
	uint64_t reverse_num = 0;
	int i;
	for (i=0; i < 64; i++)
	{
		if ((num & ((uint64_t)1 << i)))
			reverse_num = reverse_num | ((uint64_t)1 << (63 - i));
	}
	return reverse_num;
}
