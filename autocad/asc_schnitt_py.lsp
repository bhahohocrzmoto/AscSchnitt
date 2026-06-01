;;; Optional AutoCAD bridge for the Python ASC_SCHNITT exporter.
;;;
;;; This file does not load any .NET DLL. It prompts for AutoCAD points, calls the
;;; Python CLI, and then imports the generated DXF.
;;;
;;; Before loading, adjust these two paths if needed:
;;;   *asc-schnitt-python*  - python executable, usually "python" or "py"
;;;   *asc-schnitt-module*  - module invocation; keep as "-m ascschnitt" when the
;;;                           repository is on PYTHONPATH or installed/editable.

(setq *asc-schnitt-python* "python")
(setq *asc-schnitt-module* "-m ascschnitt")

(defun asc-schnitt-q (value)
  (strcat "\"" value "\"")
)

(defun asc-schnitt-num (value)
  (rtos value 2 8)
)

(defun c:ASC_SCHNITT_PY (/ ascRoot startPoint endPoint insertionPoint spacing exaggeration csvPath dxfPath commandLine)
  (setq ascRoot (getstring T "\nASC root folder: "))
  (if (= ascRoot "") (progn (princ "\nCanceled.") (exit)))

  (setq startPoint (getpoint "\nStart point of section: "))
  (setq endPoint (getpoint "\nEnd point of section: "))
  (setq spacing (getreal "\nSample spacing <1.0>: "))
  (if (null spacing) (setq spacing 1.0))
  (setq exaggeration (getreal "\nVertical exaggeration <1.0>: "))
  (if (null exaggeration) (setq exaggeration 1.0))
  (setq insertionPoint (getpoint "\nInsertion point for profile in DXF: "))

  (setq csvPath (getstring T "\nCSV output path: "))
  (setq dxfPath (getstring T "\nDXF output path: "))

  (setq commandLine
    (strcat
      *asc-schnitt-module*
      " --asc-root " (asc-schnitt-q ascRoot)
      " --start-x " (asc-schnitt-num (car startPoint))
      " --start-y " (asc-schnitt-num (cadr startPoint))
      " --end-x " (asc-schnitt-num (car endPoint))
      " --end-y " (asc-schnitt-num (cadr endPoint))
      " --spacing " (asc-schnitt-num spacing)
      " --vertical-exaggeration " (asc-schnitt-num exaggeration)
      " --insertion-x " (asc-schnitt-num (car insertionPoint))
      " --insertion-y " (asc-schnitt-num (cadr insertionPoint))
      " --csv " (asc-schnitt-q csvPath)
      " --dxf " (asc-schnitt-q dxfPath)
    )
  )

  (princ "\nRunning Python ASC_SCHNITT exporter...")
  (startapp *asc-schnitt-python* commandLine)
  (alert "Python export has been started. Click OK after it has finished, then the DXF will be imported.")
  (command "_.DXFIN" dxfPath)
  (princ "\nASC_SCHNITT_PY complete.")
  (princ)
)
