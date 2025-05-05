import win32com.client
import os


def PPTtoPDF(inputFileName, outputFileName, formatType=32):
    powerpoint = win32com.client.Dispatch("Powerpoint.Application")
    powerpoint.Visible = False  

    if outputFileName[-3:] != 'pdf':
        outputFileName = outputFileName + ".pdf"
    
    try:
        deck = powerpoint.Presentations.Open(inputFileName)
        deck.SaveAs(outputFileName, formatType)  
    except Exception as e:
        print("Error:", e)
    finally:
        if 'deck' in locals():
            deck.Close()
        powerpoint.Quit()